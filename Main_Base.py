import socket 
from time import *
import pickle
import pandas as pd
import os
import numpy as np
from PIL import Image, ImageEnhance
from threading import Thread as thread
import threading
from Comms import *
#uses comms version 2
from concurrent.futures import ThreadPoolExecutor
import scipy.fftpack
from ImageHashing import *


def log_transmission(filepath, status):
    '''Help: Update the transmission log pandas dataframe with a new entry.'''
    #add the new filepath & status to the dataframe
    captures_df.loc[len(captures_df)] = [filepath, status, f'{strftime("%b_%d_@_%-I_%M_%S_%p", localtime())}']
    #save the dataframe locally
    captures_df.to_pickle('Captures_Dataframe.p')
    captures_df.to_csv('Captures_Dataframe.csv')


#verbose is bool to toggle debugging print statements
verbose = True

#name the current machine
base_name = "Jack's Mac Mini"


#establish the maximum bytes per transmission for the network
max_bytes = 1024

#check if a database exists already, create a new one if not
if os.path.exists('Captures_Dataframe.p'):
    captures_df = pd.read_pickle('Captures_Dataframe.p')
else:
    captures_df = pd.DataFrame(columns=['Filename', 'Instance', 'Receipt Time'])
    
#create an instance folder if necessary
if not os.path.exists(f'Instances'): os.mkdir(f'Instances')


#first open a base socket instance on an available port
base_socket = open_base_socket()

#initiate a process pool to execute processes in the background
executor = ThreadPoolExecutor(max_workers=4)

#handle new clients in a thread
new_client_handler = handle_new_clients(base_socket, 'New Client Handler 0', handshake = True, verbose = True)
new_client_handler.start()
new_clients = 0

while new_client_handler.is_alive():
    #wait until a new client is detected to do anything
    if new_client_handler.is_alive():
        sleep(.1)
    
#once the new client handler thread dies, start listening
new_client_handler.end()
new_clients += 1
#initiate a new process with the connected client
client = new_client_handler.client
client_address = new_client_handler.client_address

#initiate a thread to listen on the new client
sock = socket_connection(client, client_address, verbose, f"Socket@{client_address}", max_bytes)
sock.start()

while True:
    #wait for an incoming transmission
    new_data_dict = sock.receive()
    
    #pull the data from the received dictionary
    new_type = new_data_dict['Type']
    new_source = new_data_dict['Source']
    new_content_type = new_data_dict['Content Type']
    new_data = new_data_dict['Data']
    
    #print a status update
    if verbose: print(f"New {new_content_type} transmission from {new_source}")
        
    file_name = new_data['Name']
    file_instance = new_data['Instance']
    file_bytes = new_data['File']
    
    #create a new subfolder for the instance if necessary
    if not os.path.exists(f"Instances/{file_instance}"):
        os.mkdir(f"Instances/{file_instance}")

    #save the image locally
    file_path = f"Instances/{file_instance}/{file_name}"
    with open(file_path, 'wb') as f:
        f.write(file_bytes)
        
    #log the transmission
    log_transmission(file_path, 'Received')
    if verbose: print(f"File received and saved locally @ {file_path}\n")
    
    if new_content_type == 'Video':
        #also adjust the video's brightness and resave it
        new_filepath = brighten_video(file_path, True)
        log_transmission(new_filepath, 'Edited')
        if verbose: print(f'Video edited & resaved @ {new_filepath}\n')




        '''
        #submit the new connection to the process executor
        executor.submit(run_and_handle, new_sock)
        
        #restart the thread to handle new clients
        new_client_handler = handle_new_clients(base_socket, f"New Client Handler {new_clients}", handshake = True, verbose = True)
        new_client_handler.start()
        '''

        
        
