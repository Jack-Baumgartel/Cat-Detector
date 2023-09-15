import socket 
import time
import pickle
import pandas as pd
import os
import keras_cv
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager 


#verbose is bool to toggle debugging print statements
verbose = True

#capture delay variables in seconds
fast_delay = 5
normal_delay = 15

#check if a database exists already, create a new one if not
if os.path.exists('Captures_Dataframe.p'):
    captures_df = pd.read_pickle('Captures_Dataframe.p')
else:
    captures_df = pd.DataFrame(columns=['Filename', 'Instance', 'Timestamp', 'Detections', 'Cat Likely'])
    
#create an instance folder if necessary
if not os.path.exists(f'Instances'): os.mkdir(f'Instances')


#load a pretrained object detection model
pretrained_model = keras_cv.models.YOLOV8Detector.from_preset("yolo_v8_m_pascalvoc", bounding_box_format="xyxy")

#find a suitable font to use for the text overlays on image detection
font_file = font_manager.findfont('Arial', fontext='ttf')

#note the class_ids for the model via https://github.com/fizyr/keras-retinanet/blob/main/keras_retinanet/preprocessing/pascal_voc.py
class_ids = [
    "Aeroplane",
    "Bicycle",
    "Bird",
    "Boat",
    "Bottle",
    "Bus",
    "Car",
    "Cat",
    "Chair",
    "Cow",
    "Dining Table",
    "Dog",
    "Horse",
    "Motorbike",
    "Person",
    "Potted Plant",
    "Sheep",
    "Sofa",
    "Train",
    "Tvmonitor",
    "Total",
]

#define functions to use for object detection on images

def scale_bbox(og_bbox, og_img_size, max_scaled_dim=640):
    '''Help: Given a [x0, y0, x1, y1] bounding box, an original image size, and maximum scaled dimension, scale the box (that was made
    to fit the square, scaled version) to fit the original image.
    Returns a bounding box of four integers in the same format.'''
    if og_img_size[0] >= og_img_size[1]:
        y_scaled_dim = (og_img_size[1]/og_img_size[0])*max_scaled_dim
        n_x0 = int((og_bbox[0]/max_scaled_dim)*og_img_size[0])
        n_x1 = int((og_bbox[2]/max_scaled_dim)*og_img_size[0])
        n_y0 = int((og_bbox[1]/y_scaled_dim)*og_img_size[1])
        n_y1 = int((og_bbox[3]/y_scaled_dim)*og_img_size[1])
        return [n_x0, n_y0, n_x1, n_y1]
    else:
        x_scaled_dim = (og_img_size[0]/og_img_size[1])*max_scaled_dim
        n_x0 = int((og_bbox[0]/x_scaled_dim)*og_img_size[0])
        n_x1 = int((og_bbox[2]/x_scaled_dim)*og_img_size[0])
        n_y0 = int((og_bbox[1]/max_scaled_dim)*og_img_size[1])
        n_y1 = int((og_bbox[3]/max_scaled_dim)*og_img_size[1])
        return [n_x0, n_y0, n_x1, n_y1]
        


def detect_objs(pil_img, model, class_ids):
    '''Help: Predict the objects contained in a PIL.Image instance. Given the PIL image, the loaded Keras model, and a class list,
    overlay the results onto the image and return the PIL.Image and a dictionary of the top results.
    pil_img: PIL.Image instance
    model: Keras model instance loaded from preset
    classes_ids: list of class names in order
    '''
    
    #convert the image to a numpy array
    img_arry = np.array(pil_img)
    #create a method to resize the image and then resize it
    resized_shape = (640,640)
    inference_resizing = keras_cv.layers.Resizing(
        resized_shape[0], resized_shape[1], pad_to_aspect_ratio=True, bounding_box_format="xyxy")
    image_batch = inference_resizing([img_arry])
    
    #use the model to determine image contents
    result = model.predict(image_batch, verbose=0)
    
    #add the bounding boxes to the image
    img_overlay = ImageDraw.Draw(pil_img)
    
    #create a dictionary to store detected objects
    detections = {}
    
    #loop through all detected objects
    for detection in range(result['num_detections'][0]):
        class_id = result['classes'][0][detection]
        class_name = class_ids[class_id]
        confidence = result['confidence'][0][detection]
        bbox = result['boxes'][0][detection]
        rescaled_bbox = scale_bbox(bbox, img_arry.shape[:2])
        #print(f"Detection {detection+1}: {confidence*100:.02f} {class_name} @ {bbox} : {rescaled_bbox}")
        
        #format a string to be displayed for each detection
        display_text = f"{confidence*100:.02f}% {class_name}"
        
        #add this object to the detected objects dictionary, appending "*" to the name if it already is there
        while class_name in detections.keys(): 
            class_name += '*'
        detections[class_name] = confidence
        
        #scale line thickness & y offset to match pixels in image
        lw_scaler = int(pil_img.size[0]/500)
        pad_scaler = int(pil_img.size[0]/700)
        
        #draw the rectangle around the detected object
        img_overlay.rectangle(rescaled_bbox, width=lw_scaler, outline=(255,255,255))
        #add a background to the label text
        #text_bbox = drawn_img.textbbox((int(bbox[:2][0]*1.05), int(bbox[:2][1]*1.05)), display_text, anchor='la', font=font)
        #img_overlay.rectangle(text_bbox, width=2, fill='black', outline='black')
    
        #scale the fontsize based on the size of the bounding box for each object
        fontsize = 2
        font = ImageFont.truetype(font_file, size=fontsize)
        while font.getlength(display_text) < np.abs(0.8 * (rescaled_bbox[2]-rescaled_bbox[0])):
            fontsize += 1
            font = ImageFont.truetype(font_file, size=fontsize)
            #print(f'Text length {font.getlength(display_text)} < {np.abs(0.8 * (rescaled_bbox[2]-rescaled_bbox[0]))}')
    
        #add a label to the box
        img_overlay.text((int((np.abs(rescaled_bbox[0])+np.abs(rescaled_bbox[2]))/2), int(rescaled_bbox[1]+pad_scaler)), display_text, 
                         fill='white', stroke_fill='black', stroke_width=2,
                         anchor='ma', font=font)
    
    return pil_img, detections



#establish a server socket on the local computer
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
port = 8081
s.bind(('', port))
if verbose: print(f'Socket established at {socket.gethostname()}:{port}')
#start listening for any incoming connections
s.listen(2)

max_bytes = 4096
while True:
    #accept a new connection and note the client & address
    client, client_address = s.accept()
    if verbose: print(f"\n\nConnected to {client_address[0]}:{client_address[1]}, waiting for header ...")
    
    #all new connections should first send a header message, look for it
    incoming_data = client.recv(max_bytes)
    header = pickle.loads(incoming_data)
    
    #if the incoming transmission is more than the allowed bytes, toss an error as it likely was not a header
    if len(incoming_data) >= max_bytes:
        print(f"That likely wasn't a header! ({max_bytes} bytes received)")
        break
    #also stop if the object type is not a header
    if header['Type'] != 'Header':
        print(f'Transmission received is {header["Type"]}, it must be "Header"')
        break
    
    #otherwise, interpret the header and prepare to receive the full datastream
    #parse the expected number of bites as given in the header
    expected_file_size = header['Contents']['Size']
    if expected_file_size < 1000000:
        file_size_str = f"{int(expected_file_size/1000)} KB"
    elif expected_file_size >= 1000000:
        file_size_str = f"{int(expected_file_size/1000000)} MB"   
        
    #send back confirmation to the client that the server is ready for the package
    client.send('Go'.encode())
    if verbose: print(f'Header received, and confirmed, {file_size_str} package inbound.')

    #receive data until the appropriate number of bytes is reached
    databytes = b''
    while len(databytes) < expected_file_size:
        databytes += client.recv(4096)
        percent_received = np.round(len(databytes)/expected_file_size*100, 2)
        if verbose: print(f"\r {percent_received}%  ({len(databytes)}/{expected_file_size})received", end="")
    
    #decode the data received
    data = pickle.loads(databytes)

    #if the received data type is a request, serve the request
    if data['Type'] == 'Request':
        if data['Contents'] == 'New Instance':
            if verbose: print('\nNew Instance request received.')
            #send the next integer instance value to use based on the captures dataframe
            if not len(captures_df['Instance']):
                new_instance = 1
            else:
                new_instance = max(list(captures_df['Instance']))+1
            #send the new instance value back
            client.send(f"{new_instance}".encode())
            #create the new instance folder locally if needed
            if not os.path.exists(f'Instances/{new_instance}'): os.mkdir(f'Instances/{new_instance}')
            if verbose: print(f'Instance set to {new_instance} and sent.\n')
            
    
    #if the received data is an image, save it appropriately and add it to the dataframe
    if data['Type'] == 'Image':
        img_name = data['Contents']['Name']
        img_instance = data['Contents']['Instance']
        img_timestamp = data['Contents']['Timestamp']
        img_file = data['Contents']['File']
        cat_likely = False

        if verbose: print(f'\nImage ({img_name}) received and sent for detection.')

        #detect any objects in the image
        detected_ig, detections = detect_objs(img_file, pretrained_model, class_ids)

        if verbose: print(f"Detected: {list(detections.keys())}")
        
        #save the image locally
        file_path = f"Instances/{img_instance}/{img_name}"
        detected_ig.save(file_path)

        #determine if a cat was detected with high probability
        cat_likely = False
        for key, val in detections.items():
            if not ("Cat" in key and val > .7):
                pass
            else:
                cat_likely =True
                break
                
        #and change the response accordingly
        if cat_likely: 
            response = {'delay': fast_delay, 'run': True}
            if verbose: print(f'Cat detected, setting delay to {fast_delay}s')
        else:
            response = {'delay': normal_delay, 'run': True}
            if verbose: print(f'No cats, setting delay to {normal_delay}s')
                            
        #send back the response
        client.send(pickle.dumps(response))
        if verbose: print(f'Response sent for image {img_name}')
                
        #add the entry to the dataframe (last entry is the cat-detection result)
        captures_df.loc[len(captures_df)] = [img_name, int(img_instance), img_timestamp, detections, cat_likely]

        #save the dataframe with the new entry
        captures_df.to_pickle('Captures_Dataframe.p')
        captures_df.to_csv('Captures_Dataframe.csv')
                                             
        if verbose: print(f"Image added to dataframe and saved locally @ {file_path}\n")

        
    #client.close()
    #print(f'Disconnected from {client_address}.')

