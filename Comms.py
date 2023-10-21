import socket
import os
import pickle
from time import sleep, time
import numpy as np
from threading import Thread as thread
import threading
from pprint import pprint

'''Version: 2'''

class socket_connection(thread): 
    '''Help: Subclass of threading.Thread with specific functionality to handle socket connections.
    Initiate an instance by assigning it to a variable, then run it with variable.start() as shown below:
    x = socket_connection(socket.socket object, ('192.0.168.0.4', 8080), True, "Socket Name")
    x.start()
    '''
    def __init__(self, client, address, verbose, name, max_bytes=1024):
        super().__init__()
        self.client = client
        self.client_address = address
        self.verbose = verbose
        self.name = name
        self.running = True
        self.start_time = time()
        self.thread_preface = f"\n    [{self.name}]: "
        self.max_bytes = max_bytes
        #set a timeout value for the socket at 1 min
        self.client.settimeout(60)
        
    def get_info(self):
        '''Help: Returns all available information about the particular thread'''
        thread_data = {
            'Name': self.name,
            'Client': self.client,
            'Client Address': self.client_address,
            'Verbose': self.verbose,
            'Running': self.running,
            'Start Time': self.start_time,
            'Preface': self.thread_preface,
            'Max Bytes':self.max_bytes,
            'Timeout': self.client.timeout}
        return thread_data
        
    def run(self):
        '''Help: Checks if the .end() function was called every second and ends thread if so.'''
        while self.running:
            #print('.', end='')
            sleep(1)
        return

    def send(self, data_dict, confirmation_timeout=60):
        '''Help: Transmit the provided dictionary via the socket connection. Provide the data to be transmitted as a dictionary object
        with the following format: {'Type': X, 'Content': Y, 'From': Z} where X can be any of ['Image', 'Message', 'Error], Y is another 
        dictionary object containing the data to be transmitted, and Z is the data source name.
        '''
        #first ensure the thread is alive
        if not self.running:
            self.end()
            raise Exception(f'{self.thread_preface}Thread is dead!')

        #check to ensure that the data is formatted properly with the required information
        try:
            x = data_dict['Type']
            x = data_dict['Source']
            x = data_dict['Content Type']
            x = data_dict['Data']
        except KeyError:
            print(f"{self.thread_preface}Error: Bad key, data_dict must contain at least ['Type', 'Source', 'Content Type', 'Data'] \
in data_dict.keys(), current values are {list((data_dict.keys()))}")
            return False
            
        #set the client timeout
        self.client.settimeout(confirmation_timeout)
            
        #determine if the data dictionary is small enough to send alone or if it needs a header
        transmission_bytes = pickle.dumps(data_dict)

        #if the data is too big to send alone, prepare a header first
        if len(transmission_bytes) >= self.max_bytes:
            #print an update to the user
            if self.verbose: print(f'{self.thread_preface}Transmission data is large, sending a header first ... ', end='')
                
            #prepare a header
            header_dict = {
                'Type': 'Header',
                'Size': len(transmission_bytes)}
            #convert the dict to a bytes object
            header_bytes = pickle.dumps(header_dict)

            #send the header
            self.client.sendall(header_bytes)
            #listen for confirmation message back
            try:
                header_confirmation = pickle.loads(self.client.recv(self.max_bytes))
            except socket.timeout:
                print(f'{self.thread_preface}Error: No response received after {self.client.gettimeout()}s')
                return False

            #check to ensure the header was received and a 'Go' command was sent back
            if header_confirmation != 'Go':
                raise Exception(f"{self.thread_preface}Error: 'Go' confirmation not received after header. \
Response was '{header_confirmation}'")
                return False
            #print an update to the user
            if self.verbose: print(f'Header confirmed.')
                
        #print an update to the user
        if self.verbose: print(f'{self.thread_preface}Sending transmission ... ', end='')
            
        #send the full transmission bytes
        self.client.sendall(transmission_bytes)

        #wait and listen for 'Received' message to be returned
        try:
            transmission_reply = pickle.loads(self.client.recv(self.max_bytes))
        except socket.timeout:
            print(f'{self.thread_preface}Error: No response received after {self.client.gettimeout()}s')
            return False

        #check if the proper message is returned
        if transmission_reply != 'Received':
            raise Exception(f"{self.thread_preface}Error: Transmission receipt incorrect, message back was '{transmission_reply}'")
            return False
        
        #print an update to the user
        if self.verbose: print(f'Transmission receipt confirmed.')
        return True

    def receive(self):
        '''Help: [Blocking function] Listen for incoming data from the socket. Simply returns the data after ensuring all has been received. 
        *** This method needs to be called again after successful receipt to continue listening!
        '''
        #first ensure the thread is alive
        if not self.running:
            self.end()
            raise Exception(f'{self.thread_preface}Thread is dead!')
            
        #print an update to the user
        if self.verbose: print(f'{self.thread_preface}Listening for incoming data ...')
        
        #set a relatively short timeout and make it non-blocking
        #client.settimeout(5)
        #client.setblocking(0)
        #while the thread is running, listen for any incoming bytes
        while self.running:
            try:
                #blocking: listen for up to max_bytes bytes of incoming data
                incoming_bytes = self.client.recv(self.max_bytes)
                #unpickle the data
                transmission = pickle.loads(incoming_bytes)

                #if the transmission is a header only, send back 'Go' command and wait for the full transmission
                if transmission['Type'] == 'Header':
                    #send back a 'Go' command and listen for the whole transmission
                    incoming_transmission_size = transmission['Size']
                    self.client.send(pickle.dumps('Go'))
                    
                    #print an update on the data received
                    if self.verbose: print(f'{self.thread_preface}Header received and confirmed, {incoming_transmission_size:,} bytes inbound.')

                    #receive data until the appropriate number of bytes is reached
                    databytes = b''
                    while len(databytes) < incoming_transmission_size:
                        databytes += self.client.recv(4096)
                        percent_received = np.round(len(databytes)/incoming_transmission_size*100, 2)
                        if self.verbose: print(f"\r{self.thread_preface}{percent_received}%  \
({len(databytes)}/{incoming_transmission_size}) received. ", end="")
                    
                    #once all data is received, convert the bytes back to a dict-object
                    transmission = pickle.loads(databytes)

                print('Sending receipt')
                #confirm receipt with the client
                self.client.send(pickle.dumps('Received'))

                #now the transmission data can be interpreted and returned
                transmission_type = transmission['Content Type']
                transmission_source = transmission['Source']
                #print a status update to the user
                if self.verbose: print(f"{self.thread_preface}'{transmission_type}' type transmission received from {transmission_source}.")
    
                return transmission
            
            #the socket should periodically stop listening according to the socket timeout, just pass and try again when it happens
            except socket.timeout:
                pass
        
    def end(self):
        '''Help: Ends the thread cleanly.'''
        self.running = False


class handle_new_clients(thread):
    '''Help: Subclass of threading.Thread with specific functionality to accept new socket connections to base_socket
    Initiate an instance by assigning it to a variable, then run it with variable.start() it ends when a new connection is 
    detected. Use variable.client and variable.client_address to pull info on the new connection.'''
    def __init__(self, base_socket, name, handshake, verbose):
        super().__init__()
        self.client = None
        self.client_address = None
        self.running = True
        self.name = name
        self.base_socket = base_socket
        self.handshake = handshake
        self.verbose = verbose
        
    def run(self):
        thread_preface = f"[{self.name}]: "
        if self.verbose: print(f'\n{thread_preface}Listening for new connections ...')
        #define the listening socket timeout as 5s, to periodically check if the program should be running still
        self.base_socket.settimeout(5)
        #continue to listen as long as the running variable is True
        while self.running:            
            try:
                #base_socket.accept will block code below until a new client is accepted
                client, client_address = self.base_socket.accept()
                self.client_address = client_address
                self.client = client
                #if handshake mode is on, listen for and echo an initial message
                while self.handshake:
                    data = client.recv(1024)
                    if not data: break
                    #return the handshake
                    client.sendall(data)
                    self.handshake = False
                if self.verbose: print(f"{thread_preface}New client: Socket@{client_address[0]}:{client_address[1]}")
                return
            except socket.timeout:
                pass
        print('new client handler finished running')

    def end(self):
        self.running = False


def list_network_ips(rpi=True):
    '''Help: Lists the IP address for all devices on the local network.
    Returns a list of ["ip", "ip2"]
    '''
    #first use a shell command to scour the network for devices
    devices = []
    if not rpi:
        for device in os.popen('arp -a'): devices.append(device)
    else:
        for device in os.popen('/sbin/arp -a'): devices.append(device)

    #then start a list and pull just the IP address for each one
    #list starts with the IP of the local machine
    device_list = [socket.gethostbyname(socket.gethostname()), '192.168.0.6']
    for device in devices:
        ip = device.split('(')[1].split(')')[0]
        #print(f'ip: {ip} ... ', end='')
        try:
            hostname = socket.gethostbyaddr(ip)
            #print(f'Hostname: {hostname} \n')
        except socket.herror:
            hostname = None
            #print('Hostname not found. \n')
        device_list.append(ip)
    return device_list


def open_base_socket(verbose = True, thread_preface = ''):
    '''Help: Open a socket on the local computer which others can connect to. Returns the base_socket
    instance and prints a status if verbose'''
    #establish a base_socket instance on the main computer
    base_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ports = [8080, 8081, 8082, 8083, 8084, 8085]
    for port in ports:
        try:
            base_socket.bind(('', port))
            if verbose: print(f'{thread_preface}Socket established at {socket.gethostbyname(socket.gethostname())}:{port}\n')
            break
        except OSError as error:
            if error.errno == 48:
                if verbose: print(f"{thread_preface}Port {port} busy!")
    #start listening for any incoming connections
    base_socket.listen(5)

    return base_socket


def find_base_socket(rpi = True, timeout=60, verbose = True):
    '''help: Scan the local network and attempt to connect to available sockets. If successful, returns (address, port)
    Otherwise returns (None, None)'''
    #first list all IP adresses on the network
    #network_ips = list_network_ips(rpi)
    network_ips = ['Jacks-MacBook-Air.local', 'Jackmini.local']
    
    #define ports to check
    ports = [8080, 8081, 8082, 8083, 8084, 8085]
    
    #establish a short timeout for sockets just while scanning
    scanning_timeout = 1
    socket.setdefaulttimeout(scanning_timeout)
    
    #cycle through the IP adress list
    for address in network_ips:
        #cycle through each port option
        for port in ports:
            #attempt to connect to a socket with the current port & ip adress
            try:
                if verbose: print(f"Attempting Connection @ {address}:{port} ... ", end='')
                new_sock = socket.socket()
                new_sock.connect((address, port))
                #attempt to send a handshake to the server
                if verbose: print('connected, attempting handshake ... ', end='')
                new_sock.sendall('Handshake'.encode())
                #listen for the handshake to be sent back
                data = new_sock.recv(1024)
                #close this socket, just return the server and port
                if verbose: print('success!')
                return new_sock, (address, port)
                
            except Exception as e:
                new_sock.close()
                print(f"Failed: {e}")

    return None, (None, None)  


