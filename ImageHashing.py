import numpy as np
import scipy.fftpack
from PIL import Image, ImageEnhance
import os
import cv2
from time import time, strftime, localtime, sleep
import shutil


#note where the script is running on the computer
abspath = os.path.abspath(__file__)
running_dir = os.path.dirname(abspath)

#define average pixel brightness thresholds, above and below which the photo needs editing
brightness_low_th = 50
brightness_high_th = 175


def phash(image, hash_size=32, highfreq_factor=4):
    '''Help: Accepts a PIL.Image type object and returns a hash of the image. '''
    img_size = hash_size * highfreq_factor
    image = image.convert("L").resize((img_size, img_size), Image.LANCZOS)
    pixels = np.asarray(image)
    dct = scipy.fftpack.dct(scipy.fftpack.dct(pixels, axis=0), axis=1)
    dctlowfreq = dct[:hash_size, :hash_size]
    med = np.median(dctlowfreq)
    diff = dctlowfreq > med
    return diff.flatten()
    

def hash_folder(image_folder):
    image_list = [img for img in os.listdir(image_folder) if img.endswith(".jpg")]
    image_list.sort()

    image_hash_dict = {}

    for index, img_name in enumerate(image_list):
        img_path = f"{running_dir}/{image_folder}/{img_name}"
        img_obj = Image.open(img_path)
        img_hash = phash(img_obj)
        image_hash_dict[index] = [img_name, img_hash]
        

    hash_comparisons = {}

    for index in list(image_hash_dict.keys())[1:]:
        prior_hash = image_hash_dict[index-1][1]
        prior_name = image_hash_dict[index-1][0]
        current_hash = image_hash_dict[index][1]
        current_name = image_hash_dict[index][0]
        
        difference_array = np.equal(prior_hash, current_hash)
        percent_alike = np.round(sum(difference_array)/len(difference_array)*100, 2)
        hash_comparisons[index] = f"{percent_alike}% similarity for {prior_name} vs. {current_name}"
        
        print(hash_comparisons[index])
        
    return hash_comparisons


def format_time(seconds):
    '''Help: Given an time in seconds, format it as a nice string.
    EG. foramt_time(134.45) would return "2 min & 14.45s"
    '''
    if seconds < 0:
        raise ValueError('Number of seconds cannot be negative!')
    elif 0 <= seconds <= 60:
        min = None
        hours = None
        remaining_s = np.round(seconds, 2)
    elif 60 < seconds < 3600:
        hours = None
        min = int(seconds/60)
        remaining_s = np.round(seconds-min*60, 2)
    else:
        hours = int(seconds/3600)
        min = int((seconds - hours*3600)/60)
        remaining_s = np.round(seconds-min*60-hours*3600, 2)
    
    #create an empty string to add our time values to
    time_str = ''
    if hours:
        if hours != 1:
            time_str += f"{hours} hours, "
        elif hours == 1:
            time_str += f"{hours} hour, "
    if min:
        time_str += f"{min} min & "

    time_str += f"{remaining_s}s"
    
    return time_str

    
def adjust_img(img_obj, verbose = True):
    '''Help: Given an image as a numpy array or PIL.Image, correct it's average brightness level to a medium value if the image is too dark or light.
    Returns an image of either numpy array or PIL.Image type, whichever was provided to start.'''
    
    #check if an array was provided
    if type(img_obj) == np.ndarray:
        #note that an array was provided originally and will thus need to be returned
        array_type = True
        
        #get the average brightness value of all pixels in the image
        img_brightness = img_obj.mean()
        
        #reformat the cv2 array to be RGB instead of the default BGR
        recolored_img = cv2.cvtColor(img_obj, cv2.COLOR_BGR2RGB)
        #convert the numpy array to a PIL image
        img_obj = Image.fromarray(recolored_img)
        
        if verbose: print(f'cv2 image received of brightness {img_brightness}')

    #if the provided image was already a PIL object, no need to convert
    else:
        #note that array was not provided originally and will thus not need to be returned
        array_type = False
        #get the average brightness value of all pixels in the image
        img_brightness = np.array(img_obj, dtype=int).mean()
        
        if verbose: print(f'PIL image received of brightness {img_brightness}')
        
    #now adjust the PIL.Image object's brightness as desired

    #set a cap after which the program exits
    cap = 1
    edit_count = 0

    #if the image is too dark, brighten it
    while img_brightness < brightness_low_th and edit_count < cap:
        correction_factor = float((brightness_low_th - img_brightness)/8+1)
        img_obj = ImageEnhance.Contrast(img_obj).enhance(.5)
        img_obj = ImageEnhance.Brightness(img_obj).enhance(correction_factor)
        
        img_brightness = np.array(img_obj, dtype=int).mean()
        if verbose: print(f'Brightness increased to {img_brightness}')
        edit_count += 1
        
    edit_count = 0
    #if the image is too bright, darken it
    while img_brightness > brightness_high_th and edit_count < cap:
        correction_factor = float(1-(img_brightness - brightness_high_th)/(255-brightness_high_th))
        img_obj = ImageEnhance.Brightness(img_obj).enhance(correction_factor)
        img_obj = ImageEnhance.Contrast(img_obj).enhance(3)
        img_brightness = np.array(img_obj, dtype=int).mean()
        if verbose: print(f'Brightness decreased to {img_brightness}')
        edit_count += 1
        
    if array_type:
        #finally reconvert the PIL.Image to a numpy array with proper coloring
        img_obj = cv2.cvtColor(np.array(img_obj), cv2.COLOR_RGB2BGR)
        
        if verbose: print(f'cv2 image returned.')
        return img_obj
        
    else:
        if verbose: print(f'PIL Image returned.')
        return img_obj
    


def progress_bar(percent_done, bar_length):
    '''Help: Returns a string that looks like a progress bar given a percentage complete and a desired length
    of the bar. EG. progress_bar(50, 10) would return "*****-----"
    '''
    stars = int(percent_done/100*bar_length)
    return "|"+("*"*stars)+"-"*(bar_length-stars)+"|"
    

def brighten_video(path_to_vid, verbose=True):
    '''Help: Self contained function to adjust the brightness of a video file by editing it frame by frame.'''
    start_time = time()
    vid_abs_path = f"{running_dir}/{path_to_vid}"
    #create a new folder for this video's frames, deleting any old folder first
    frame_folder = f'{running_dir}/Frames'
    if os.path.exists(frame_folder):
        shutil.rmtree(frame_folder)
    os.mkdir(frame_folder)
    
            
    #iniitate a videocapture instance with the video file and read the first frame
    vidcap = cv2.VideoCapture(vid_abs_path)
    #determine the total number of frames in the video and the frame rate
    total_frames = int(vidcap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_rate = vidcap.get(cv2.CAP_PROP_FPS)
    
    #let user know whats going on
    if verbose: print(f"\n{total_frames} frames ({frame_rate} fps) found from {path_to_vid}, extracting now ... ")
    #load the first frame
    success, frame = vidcap.read()
    frame_count = 1
    #loop through all available frames in the video and save them under the appropriate folder
    while success:
        #save the latest frame with 7 padded 0s
        cv2.imwrite(f"{frame_folder}/{frame_count:07}.jpg", frame)
        #provide feeback on that progress
        percent_done = np.round(frame_count/total_frames*100, 2)
        if verbose: print(f'\r    Frame {frame_count}/{total_frames} {progress_bar(percent_done, 50)} {percent_done}%', end='')
        #read the next frame
        success, frame = vidcap.read()
        frame_count += 1
    #when finished, print a final message with the results
    elapsed_time = format_time(time()-start_time)
    frame_speed = format_time((time()-start_time)/frame_count)
    if verbose: print(f'\nSaved {frame_count-1} images in {elapsed_time} ({frame_speed} per frame)\n')

    #sift through the images subfolder and make a list of all images within
    images = [img for img in os.listdir(frame_folder) if img.endswith(".jpg")]
    images.sort()
    num_images = len(images)
    
    #if verbose: print(f'{num_images} images found.')
    
    #determine if any editing is actually necessary by first sampling 3 frames from the video
    adjustments_necessary = False
    test_frames = [int(num_images*.25), int(num_images*.5), int(num_images*.75)]
    for frame_index in test_frames:
        image_filename = images[frame_index]
        image_path = os.path.join(frame_folder, image_filename)
        img = cv2.imread(image_path)
        brightness = img.mean()
        if not brightness_low_th < brightness < brightness_high_th:
            adjustments_necessary = True
    
    if not adjustments_necessary:
        if verbose: print('Video adjustments not necessary.')
        return vid_abs_path
    else:
        #determine canvas size of the provided images (pixel dimensions of images)
        canvas_size = tuple(reversed(cv2.imread(os.path.join(frame_folder, images[0])).shape[:2]))
        
        #initiate a videowriter instance to save the video
        resulting_video_path = f"{path_to_vid.split('.')[0]}_adjusted.mp4"
        out = cv2.VideoWriter(resulting_video_path, cv2.VideoWriter_fourcc(*'avc1'), 30, canvas_size) #or use 'MP4V'
        
        if verbose: print(f'Editing frames & compiling video of size {canvas_size}  estimated video length = {num_images/frame_rate}s ...')
        
        #loop through the images and add each one to the video
        frame_start_time = time()
        for index, filename in enumerate(images):
            #open the image and save write it to the video
            img_path = os.path.join(frame_folder, filename)
            img = cv2.imread(img_path)
            adjusted_img = adjust_img(img, verbose=False)
            out.write(adjusted_img)
            percent_done = np.round((index+1)/num_images*100, 2)
            if verbose: print(f'\r    Frame {index+1}/{num_images} {progress_bar(percent_done, 50)} {percent_done}%', end='')
        
        #provide some metrics
        elapsed_time = format_time(time()-frame_start_time)
        frame_speed = format_time((time()-frame_start_time)/(index+1))
        if verbose: print(f'\nWrote {index+1} images in {elapsed_time} ({frame_speed} per frame) Saving video now ...\n')
        
        #now save the actual video file
        out.release()
        elapsed_time = format_time(time()-start_time)
        if verbose: print(f"Result.mp4 video file edited & saved after a total time of {elapsed_time}")
        
        #delete the folder of image frames
        shutil.rmtree(frame_folder)
        
        return resulting_video_path


def brighten_vids(vid_folder):
    '''Help: brighten each mp4 video in the provided folder.'''
    vid_list = [vid for vid in os.listdir(vid_folder) if vid.endswith(".mp4")]
    vid_list.sort()
    
    for vid in vid_list:
        video_path = f"{vid_folder}/{vid}"
        
        result = brighten_video(video_path)
        
        print(f"\nVideo finished: {result}\n\n\n")
    



'''Install notes:
     - RPI installation of opencv/cv2 can be done with "sudo apt install python3-opencv"
'''





