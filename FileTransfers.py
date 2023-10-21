import inotify.adapters
from Comms import *
#uses Comms version 2
import os
from time import *
import pprint
import pandas as pd


def get_file_list(top_directory):
    '''Help: Walk through the provided directory and list all files within. Returns a list object of the path to each file.'''
    file_list = []
    for (root, dirs, files) in os.walk(top_directory):
        for file in files:
            file_list.append(f"{root}/{file}")
    return file_list

def log_transmission(filepath, status):
    '''Help: Update the transmission log pandas dataframe with a new entry.'''
    #add the new filepath & status to the dataframe
    past_transmissions.loc[len(past_transmissions)] = [filepath, status, f'{strftime("%b_%d_@_%-I_%M_%S_%p", localtime())}']
    #save the dataframe locally
    past_transmissions.to_pickle('Past_Transmissions.p')
    past_transmissions.to_csv('Past_Transmissions.csv')
        

def transmit_file(filepath):
    '''Help: Attempt to transmit a file using the conn_sock socket connection.'''
    #discern the filename and instance
    filename = filepath.split('/')[-1]
    instance = filepath.split('/')[-2]
    
    if filename.endswith('mp4'):
        content_type = 'Video'
    elif filename.endswith('jpg'):
        content_type = 'Image'
    else:
        print(f'Skipping: {filepath} (not a valid file type)')
        return False
        
    #provide a status update and update the dataframe accordingly
    print(f'Transmitting: {filepath} ...', end='')
    log_transmission(filepath, 'Attempted')

    #reload the file into memory as a bytes object
    file = open(filepath, "rb").read()
    
    #format a dictionary object for the file
    file_dict = {
    'Type':'Transmission',
    'Source': mach_name,
    'Content Type': content_type,
    'Data': {
        'Name': filename,
        'Instance': instance,
        'File': file}}
        
    #send the file dictionary
    result = comm_sock.send(file_dict, confirmation_timeout=200)
    if result:
        os.remove(filepath)
        print('sent & confirmed, local file deleted.\n')
        log_transmission(filepath, 'Transmitted')
        return True
    else:
        log_transmission(filepath, 'Failed')
        print('sent but receipt not confirmed. Error likely.')
        return False


#determine where the program file is stored
abs_path = '/home/admin/Desktop/Cat_Detect_8'

#set the machine source name
mach_name = 'RPI 1'

#attempt to run the program, try again for any unhandled exception
while True:
    try:
        #attempt to connect to a base socket
        base_sock = None
        while base_sock == None:
            #attempt to find an open socket on the network, returns None if not found
            base_sock, base_address = find_base_socket()
            
            if base_sock == None:
                #wait a minute until next attempt
                print('No base socket found, sleeping for 1 min.')
                sleep(60)

        #once a socket has been found, initiate a socket connection instance
        comm_sock = socket_connection(base_sock, base_address, True, 'Base Socket')
        comm_sock.start()
        print('\nBase socket found:')
        pprint.pprint(comm_sock.get_info())
        print('\n')
        
        #load the list of files already sent or make it if necessary
        if os.path.exists('Past_Transmissions.p'):
            past_transmissions = pd.read_pickle('Past_Transmissions.p')
        else:
            past_transmissions = pd.DataFrame(columns=['Filepath', 'Status', 'Log Time'])

        #sift through all of the files currently in the instances directory and attempt to send them, including subfolders and their contents
        instances_folder = f'{abs_path}/Instances'
        existing_files = get_file_list(instances_folder)
        
        #update the user
        print(f'{len(existing_files)} existing files found under {instances_folder}')
        
        files_not_sent = []
        #send all existing files first
        for filepath in existing_files:
            #attempt to transmit each file
             result = transmit_file(filepath)
             #if the transmission failed, add the file to the list
             if not result:
                 files_not_sent.append(filepath)
                
        #let the user know any files not printed
        pprint.pprint(files_not_sent)
        
        #initiate a watcher for the subfolder "instances"
        i = inotify.adapters.InotifyTree(instances_folder)

        for event in i.event_gen(yield_nones=False):
            (_, [event_type], event_path, event_file_name) = event
            
            #look specifically for jpg or mp4 files to be closed
            if "IN_CLOSE" in event_type and (event_file_name.endswith('jpg') or event_file_name.endswith('mp4')):
                print(f"\n\nClose type detected on {event_path}/{event_file_name}")
                
                #store the closed filepath
                filepath = f"{event_path}/{event_file_name}"
                
                #attempt to send the file
                result = transmit_file(filepath)
                #if the transmission failed, add the file to the list
                if not result:
                    print(f"Failed to send {filepath}\n\n")
                else:
                    print(f"Sent & deleted {filepath}\n\n")
            else:
                print(f"Event type: {event_type} detected on {event_path}/{event_file_name}")
    
    except Exception as e:
        print(e)
        pass

