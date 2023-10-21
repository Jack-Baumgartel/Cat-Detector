print('Loading dependencies ...')
from time import strftime, localtime, time, sleep
import pandas as pd
import socket
from PIL import Image, ImageEnhance
import pickle
import numpy as np
import picamera2 as picam
import os
#from Comms import *
from ImageHashing import *
import signal
import sys

#simple function and listners to cleanly close the program on a kill command
def close_program(*args):
    print('\n\nProgram killed.\n\n')
    sys.exit(0)
signal.signal(signal.SIGINT, close_program)
signal.signal(signal.SIGTERM, close_program)

#note the new startup
print(f'\n\n\n ---------------------------\n Program started: {strftime("%b_%d_%-I_%M_%S_%p", localtime())}.\n ---------------------------\n\n')

#crontab scripts run weird, so add the path of any functions that are not available
# you can find such paths using "command -v x" where x is the function or library
#PATH=$PATH:/usr/sbin

#add a delay to ensure the RPI is fully awake and connected
sleep(30)

#enable HDR on the camera
os.popen("v4l2-ctl --set-ctrl wide_dynamic_range=1 -d /dev/v4l-subdev0")

#set the machine source name
mach_name = 'RPI 1'

#set a capture delay
delay = .5

#determine where the program file is stored
abs_path = '/home/admin/Desktop/Cat_Detect_8'
#abs_path = os.getcwd()

#create a new instance folder if necessary
instances_folder = f"{abs_path}/Instances"
if not os.path.exists(instances_folder): os.mkdir(instances_folder)

#look for any prior instance folders that arent empty, and set the current instance to the next available integer
prior_instances = [int(instance.name) for instance in os.scandir(instances_folder) if instance.is_dir() and os.listdir(instance.path)]
current_instance = len(prior_instances)+1

#create a new instance folder
instance_folder = f"{instances_folder}/{current_instance}"
if not os.path.exists(instance_folder):
    os.mkdir(instance_folder)
    #also make subfolders for image & video captures
    #os.mkdir(f"{instance_folder}/Images")
    #os.mkdir(f"{instance_folder}/Videos")
    
print(f'New instance folder made @ {instance_folder}\n')

#initiate the camera instance
cam = picam.Picamera2()
#set up a high-resolution configuration for stills
high_res = cam.create_still_configuration({"size":(1920, 1080)})
#max size is (4608, 2592), conservative size is 1777, 1000
#also create a video configuration
vid_conf = cam.create_video_configuration({"size":(1920, 1080)}, controls={"AnalogueGain":12})

#configure the camera instance to use the video configuration
cam.configure(high_res)
cam.start()
#allow the camera to wake up for a second
sleep(1)

#now run the program continuously
start_time = time()
mode = 'Image'
prior_hash = np.array([])
prior_img = None
prior_name = None
while True:
    #if delay seconds have not yet passed, do nothing
    if (time() - start_time) < delay:
        pass
    #otherwise capture an image anc compare it to the last one in memory
    #reset the timer
    start_time = time()
    #capture the image, name it, and adjust the brightness if necessary
    img = cam.capture_image()
    #name it with a timestamp
    img_name = f'{strftime("%b_%d_@_%-I_%M_%S_%p", localtime())}.jpg'
    print(f'Capturing image {img_name} ... ', end='')
    #edit the image brightness if necessary
    enhanced_img = adjust_img(img, verbose=False)
    
    #hash the current image object
    img_hash = phash(enhanced_img)
    
    #if there is nothing to compare the current hash to, pass
    if len(prior_hash) == 0:
        prior_img = enhanced_img
        prior_name = img_name
        prior_hash = img_hash
        print("done. No prior image for comparison.")
        pass
    else:
        #if a prior hash is in memory, compare it to the current image hash for similarity
        difference_array = np.equal(prior_hash, img_hash)
        percent_alike = np.round(sum(difference_array)/len(difference_array)*100, 2)
        print(f"{percent_alike}% unchanged.")
        
        #if significant change is present, save the current & prior images and switch to video mode
        if percent_alike < 90:
            #save the prior and current image to files
            prior_img.save(f'{instance_folder}/{prior_name}')
            enhanced_img.save(f'{instance_folder}/{img_name}')
            mode = 'Video'
            
            #record a video!!
            vid_name = f'{strftime("%b_%d_@_%-I_%M_%S_%p", localtime())}.mp4'
            print('\nVideo capture initiated ... ', end='')
            vid_save_location = f'{instance_folder}/{vid_name}'
            utc_timestamp = time()
            cam.switch_mode(vid_conf)
            cam.start()
            cam.start_and_record_video(vid_save_location, duration=70)
            print(f'and saved as {vid_save_location}\n')
            
            #set the mode back to images and reset the hash to check for movement again
            cam.switch_mode(high_res)
            prior_hash = np.array([])
            
        #otherwise store the current image in memory for next iteration
        else:
            #store the current image in memory for potential later use
            prior_img = enhanced_img
            prior_name = img_name
            prior_hash = img_hash


'''Program runs on boot due to a line in crontab, to edit, enter "crontab -e" into a terminal window and add the following
"@reboot LIBCAMERA_LOG_LEVELS=WARN python /home/admin/Desktop/Cat_Detect_8/Main_RPI.py >> /home/admin/Desktop/Cat_Detect_8/Main_RPI.log 2>&1"

* "LIBCAMERA_LOG_LEVELS=WARN" prefix suppresses informational libcamera console output. Exclude that text to get full info from the camera object


To find and stop the program when it's running from boot, use "ps -ef | grep python" to list running python scripts, then get the PID of the most likely script, and run "kill <PID>" where <PID> is likely 253 or another integer.
'''













