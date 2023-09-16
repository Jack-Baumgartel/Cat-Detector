import pandas as pd
import socket
import time
from PIL import Image, ImageEnhance
import pickle
from time import strftime, localtime, time, sleep
import numpy as np
import picamera2 as picam

#add a delay to ensure the RPI is fully awake and connected
sleep(30)

#note for the log file the new startup
print(f'\n\n\n ---------------------------\n Program started: {strftime("%b_%d_%-I_%M_%S_%p", localtime())}')

def send_img(img_obj, name, instance, address, port, verbose = True):
    '''Help: Send an image to another computer via the provided socket connection. 
    Provide:
    img_obj: a PIL.Image instance
    name: string, name of the image file EG. "Cat_01.jpg"
    instance: int or string, the current system instance
    socket_conn: socket.socket instance connected to a server
    verbose: boolean, toggles print statements for debugging'''
    
    #connect to the socket
    socket_conn = socket.socket()
    socket_conn.connect((address, port))
    timeout = 60
    socket_conn.settimeout(timeout)
    print(f'Socket connected at {address}:{port} with timeout of {timeout}s')
    
    
    #prepare the data as a dictionary object, convert to bytes
    img_dict = {'Type': 'Image',
                 'Contents': {'Name': str(name),
                              'Instance': int(instance),
                              'Timestamp': strftime("%b_%d_%-I_%M_%S_%p", localtime()),
                              'File': img_obj}}
    img_bytes = pickle.dumps(img_dict)
    
    #then prepare the header message to be sent first and convert to bytes
    header_msg = {'Type': 'Header',
                 'Contents': {'Size': len(img_bytes)}}
    header_bytes = pickle.dumps(header_msg)
    
    if verbose: print(f"Image bytes & header prepared")
    
    #send the header
    socket_conn.send(header_bytes)
    if verbose: print(f'Header sent.')
        
    #receive back confirmation before sending the full package
    try:
        header_confirmation = socket_conn.recv(4096).decode()
        if verbose: print('Header confirmed.')
    except socket.timeout:
        print(f'ERROR: No confirmation received after {socket_conn.gettimeout()}s')
    
    #if the header was received properly, send the file package and wait for a response before closing the connection
    if header_confirmation == 'Go':
        if verbose: print(f'Sending image ...')
        socket_conn.sendall(img_bytes)
        if verbose: print(f'Done. Waiting {timeout}s for response.')

        #await the response to the sent image
        try:
            response = pickle.loads(socket_conn.recv(4096))
            print(f"Response received.")
            return response
        except socket.timeout:
            print(f'ERROR: No confirmation received after {socket_conn.gettimeout()}s')
            return None

        socket_conn.close()
        if verbose: print('Connection closed.')

    else:
        if verbose: print('Header not confirmed.')
        socket_conn.close()
        if verbose: print("Connection closed.")
        return None



def adjust_img(img_obj):
    '''Help: Given a PIL.Image object, correct it's average brightness level to a medium value if the image is too dark or light.
    Returns a PIL.Image object.'''

    #define average pixel brightness thresholds, above and below which the photo needs editing
    brightness_low_th = 50
    brightness_high_th = 200

    #get the average brightness value of all pixels in the image
    img_brightness = np.array(img_obj, dtype=int).flatten().mean()

    #if the image is too dark, brighten it
    if img_brightness < brightness_low_th:
        correction_factor = float((brightness_low_th - img_brightness)/8+1)
        enhanced_img = ImageEnhance.Brightness(img_obj).enhance(correction_factor)

    #if the image is too bright, darken it
    elif img_brightness > brightness_high_th:
        correction_factor = float(1-(img_brightness - brightness_high_th)/50)
        enhanced_img = ImageEnhance.Brightness(img_obj).enhance(correction_factor)

    else:
        enhanced_img = img_obj
        
    return enhanced_img



#initialize the socket to send data
c = socket.socket()
address = 'Jackmini.local'
port = 8081
c.connect((address, port))
print(f'Initial socket connected at {address}:{port}')
#set a maximum waiting time until an error is reported
c.settimeout(15)


#prepare an intial request to get a new instance variable
new_instance_req = {'Type':'Request',
                    'Contents':'New Instance'}
new_instance_req_bytes = pickle.dumps(new_instance_req)

#prepare the header message and convert to bytes
header_msg = {'Type': 'Header',
             'Contents': {'Size': len(new_instance_req_bytes)}}
header_bytes = pickle.dumps(header_msg)


#send the new instance request header and wait for confirmation
c.send(header_bytes)
print('Instance request header sent.')
try:
    header_confirmation = c.recv(4096).decode()
    print('Header confirmation received.')
except socket.timeout:
    print(f'ERROR: No confirmation received after {c.gettimeout()}s')


#if the header was received properly, send the file package and wait for the response
if header_confirmation == 'Go':
    print(f'Header confirmation is: "{header_confirmation}", sending package')
    c.send(new_instance_req_bytes)
    print('Instance request package sent.')
    try:
        current_instance = c.recv(4096).decode()
        print(f'Response received, new instance set to {current_instance}\n')
    except socket.timeout:
        print(f'ERROR: No confirmation received after {c.gettimeout()}s')
    #c.close()
    #print('Closed connection')

#set up the camera instance
cam = picam.Picamera2()
#set up a high-resolution configuration 
high_res = cam.create_still_configuration({"size":(1777, 1000)})
#configure the camera instance to use the high-res configuration and start the camera
cam.configure(high_res)
cam.start()

#run the main program to continually capture and send photos
run = True #variable to neatly close the program
delay = 1 #variable to control the minimum time between image captures
start_time = time()
while run:
    #after the delay (s) has passed, capture a photo and send it to the base station
    if (time() - start_time) > delay:
        img_start_time = time()
        img = cam.capture_image()
        img_name = f'{strftime("%b_%d_@_%-I_%M_%S_%p", localtime())}.jpg'
        enhanced_img = adjust_img(img)
        
        print(f"\nImage ({img_name}) captured & enhanced, sending to main station ...")
        response = send_img(enhanced_img, img_name, current_instance, address, port)
        
        #set the run & delay variables as provided in the response
        run = response['run']
        if response['delay']: 
            delay = response['delay']
            print(f"Delay set to {delay}s.")
        print(f"Process completed in {np.round(time() - img_start_time, 1)}s\n")

        #reset the start time counter
        start_time = time()

'''Program runs on boot due to a line in crontab, to edit, enter "crontab -e" into a terminal window and add the following
"@reboot python /home/admin/Desktop/Cat_Detector_4/Main_RPI.py >> /home/admin/Desktop/Cat_Detector_4/Main_RPI.log 2>&1"
'''


