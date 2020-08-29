from socket import *
import pickle
import threading
import sys

LOCALHOST = '127.0.0.1'
BUFFER_SIZE = 2048
SERVER_COMMAND_CHANNEL_PORT = 8000
SERVER_DATA_CHANNEL_PORT = 8001

class Client:
    commandSocket = None
    dataSocket = None

    def sendCommand(self):
        command = input()
        self.commandSocket.send(command.encode())

    def getResponse(self):
        response = self.commandSocket.recv(BUFFER_SIZE).decode()
        print(response)
        tokens = response.split()
        statusCode = int(tokens[0])
        return statusCode

    def getData(self):
        response = self.dataSocket.recv(BUFFER_SIZE).decode()

        # Check data type
        if response.split()[0] == 'list':
            print(response[5:])
        elif response.split()[0] == 'file':
            f = open(response.split()[1], "w")
            f.write(" ".join(response.split()[2:]))

    def run(self):
        # Client command socket
        self.commandSocket = socket(AF_INET, SOCK_STREAM)
        self.commandSocket.connect((LOCALHOST, SERVER_COMMAND_CHANNEL_PORT))

        # Clinet data socket
        self.dataSocket = socket(AF_INET, SOCK_STREAM)
        self.dataSocket.connect((LOCALHOST, SERVER_DATA_CHANNEL_PORT))
        while True:
            self.sendCommand()
            statusCode = self.getResponse()
            if statusCode == 221:
                break # Quit
            elif statusCode == 226:
                # Recive data from data channel
                t2 = threading.Thread(target=self.getData)
                t2.start()
        
        # Quit
        self.commandSocket.close()
        self.dataSocket.close()



client = Client()
client.run()