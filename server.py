from socket import *
from user import User
import json
import threading
import os
import pathlib
import time
import pickle
import base64
import shutil

BACKLOG = 5
BUFFER_SIZE = 2048
HELP_TEXT = ("214\n"
            "USER [name], Its argument is used to specify the user's string. It is used for user authentication.\n"
            "PASS [password], Its argument is used to specify the user's password. befor this command, username must be identified using USER command."
            "PWD, Returns current working directory path.\n"
            "MKD [name], Make a new directory in server with name argument. if it has -i attribute, it make a new file in server with name argument\n"
            "RMD [name], Delete file in current directory with name argument. if it has -f attribute, it will delete directory with name argument\n"
            "LIST, Show directories and files in current directory.\n"
            "CWD [path], Changes directory to its argument. return to parent dir if argumnet is .. and returns to server main directory if it doesn't have argument.\n"
            "DL [name], Download file with name argument.\n"
            "HELP, Show commands instruction.\n"
            "QUIT, disconnect from server and will end client process.")

class Server:
    enableAccounting = False
    enableLogging = False
    enableAuthorization = False
    commandChannelPort = None
    dataChannelPort = None
    loggingPath = None
    threshold = None
    commandSocket = None
    dataSocket = None
    files = []
    users = []

    def __init__(self, configData):
        self.configServer(configData)

    def configServer(self, configData):
        # Set connection ports
        self.commandChannelPort = configData['commandChannelPort']
        self.dataChannelPort = configData['dataChannelPort']

        # Set users information
        for user in configData['users']:
           newUser = User(user['user'], user['password'])
           self.users.append(newUser)

        # Set accounting information
        accountingData = configData['accounting']
        self.enableAccounting = accountingData['enable']
        self.threshold = accountingData['threshold']
        for user in accountingData['users']:
            found = False
            for u in self.users:
                if (u.user == user['user']):
                    found = True
                    u.size = int(user['size'])
                    u.email = user['email']
                    u.alert = user['alert']
            
        # Set logging information
        loggingData = configData['logging']
        self.enableLogging = loggingData['enable']
        self.loggingPath = loggingData['path']

        # Set authorization information
        authorizationData = configData['authorization']
        self.enableAuthorization = authorizationData['enable']
        adminsData = authorizationData['admins']
        for username in adminsData:
            for u in self.users:
                if u.user == username:
                    u.isAdmin = True
        filesData = authorizationData['files']
        for filePath in filesData:
            self.files.append(filePath)

    def testConfigPrint(self):
        print(self.commandChannelPort)
        print(self.dataChannelPort)
        print(self.files)
        print(self.threshold)
        print(self.enableAccounting)
        print(self.enableAuthorization)
        print(self.enableLogging)
        for user in self.users:
            print(user.user, user.password, user.email, user.size, user.alert, user.isAdmin)
          
    def run(self):
        self.commandSocket = socket(AF_INET, SOCK_STREAM)
        self.commandSocket.bind(('', self.commandChannelPort))
        print('.:. Server is online on port', self.commandChannelPort)

        self.dataSocket = socket(AF_INET, SOCK_STREAM)
        self.dataSocket.bind(('', self.dataChannelPort))
        print('.:. Data channel is ready on port', self.dataChannelPort)
        try:
            self.commandSocket.listen(BACKLOG)
            self.dataSocket.listen(BACKLOG)
            while True:
                clientSocket, address = self.commandSocket.accept()
                print(address, 'Connected to server.')
                clientDataSocket, address = self.dataSocket.accept()
                print(address, 'connected to data channel.')
                t = threading.Thread(target=self.handleClient, args=(clientSocket, clientDataSocket))
                t.start()
        except:
            self.commandSocket.shutdown()

    def handleClient(self, clientSocket, clientDataSocket):
        userObject = User('', '', requestedForLogin=False)
        while True:
            try:
                command = clientSocket.recv(BUFFER_SIZE).decode()
            except: 
                break
            handlerOut = self.commandHandler(command, clientSocket, userObject, clientDataSocket)
            if handlerOut == 1:
                break
        clientSocket.close()

    def commandHandler(self, command, clientSocket, userObject, clientDataSocket):
        tokens = command.split()
        if len(tokens) == 0:
            clientSocket.sendall(b'501 Syntax error in parameters or arguments.')
            return
        firstToken = tokens[0]
        if firstToken == 'USER':
            self.handleUSER(tokens, clientSocket, userObject)
        elif firstToken == 'PASS':
            self.handlePASS(tokens, clientSocket, userObject)

        # User logged in
        elif userObject.isLoggedin == True:
            if firstToken == 'PWD':
                self.handlePWD(tokens, clientSocket, userObject)
            elif firstToken == 'MKD':
                self.handleMKD(tokens, clientSocket, userObject)
            elif firstToken == 'RMD':
                self.handleRMD(tokens, clientSocket, userObject)
            elif firstToken == 'LIST':
                self.handleLIST(tokens, clientSocket, userObject, clientDataSocket)
            elif firstToken == 'CWD':
                self.handleCWD(tokens, clientSocket, userObject)
            elif firstToken == 'DL':
                self.handleDL(tokens, clientSocket, userObject, clientDataSocket)
            elif firstToken == 'HELP':
                self.handleHELP(tokens, clientSocket, userObject)
            elif firstToken == 'QUIT':
                self.printLog(userObject.user + ' Quited.')
                clientSocket.sendall(b'221 Successful Quit.')
                return 1
            else:
                clientSocket.sendall(b'501 Syntax error in parameters or arguments.')

        # User not logged in
        else:
            clientSocket.sendall(b'332 Need account for login.')
        return 0

    def handleUSER(self, tokens, clientSocket, userObject):
        for user in self.users:
            if user.user == tokens[1]:
                userObject.user = user.user
                userObject.password = user.password
                userObject.email = user.email
                userObject.size = user.size
                userObject.isAdmin = user.isAdmin
                userObject.alert = user.alert
                userObject.isLoggedin = False
                userObject.currentDirectory = '.'
        userObject.requestedForLogin = True
        clientSocket.sendall(b'331 User name okay, need password.')

    def handlePASS(self, tokens, clientSocket, userObject):
        if userObject.isLoggedin == True or userObject.requestedForLogin == False:
            clientSocket.sendall(b'503 Bad sequence of commands.')
        elif userObject.user != None:
            if userObject.password == tokens[1]:
                self.printLog(userObject.user + ' logged in.')
                userObject.isLoggedin = True
                clientSocket.sendall(b'230 User logged in, proceed.')
            else:
                clientSocket.sendall(b'430 Invalid username or password.')
        else:
            if userObject.requestedForLogin == True:
                clientSocket.sendall(b'430 Invalid username or password.')
            else:
                clientSocket.sendall(b'503 Bad sequence of commands.')

    def handlePWD(self, tokens, clientSocket, userObject):
        if len(tokens) != 1:
            clientSocket.sendall(b'501 Syntax error in parameters or arguments.')
            return
        if userObject.currentDirectory == '.':
            response = '257 ' + '/'
        else:
            response = '257 ' + userObject.currentDirectory
        clientSocket.sendall(str.encode(response))
        
    def handleMKD(self, tokens, clientSocket, userObject):
        # MKD <name>
        if tokens[1] != '-i':
            if '/' in tokens[1]:
                clientSocket.sendall(b'500 Error.')
                return
            if userObject.currentDirectory == '.':
                directory = (os.path.join(os.getcwd(), tokens[1])).replace('\\', '/')
                if not os.path.exists(directory):
                    os.mkdir(directory)
                    self.printLog(userObject.user + ' created new directory named ' + tokens[1] + ' in ' + userObject.currentDirectory)
                else:
                    clientSocket.sendall(b'500 Error.')
                    return
            elif userObject.currentDirectory != '.':
                directory = (os.getcwd() + os.path.join(userObject.currentDirectory, tokens[1])).replace('\\', '/')
                if not os.path.exists(directory):
                    os.mkdir(directory)
                    self.printLog(userObject.user + ' created new directory named ' + tokens[1] + ' in ' + userObject.currentDirectory)
                else:
                    clientSocket.sendall(b'500 Error.')
                    return

            msg = '257 ' + tokens[1] + ' created.'
            clientSocket.sendall(str.encode(msg))

        # MKD -i <name>
        elif tokens[1] == '-i':
            if userObject.currentDirectory == '.':
                file = (os.path.join(os.getcwd(), tokens[2])).replace('\\', '/')
                try:
                    f = open(file, "x")
                    self.printLog(userObject.user + ' created new file named ' + tokens[2] + ' in ' + userObject.currentDirectory)
                except:
                    clientSocket.sendall(b'500 Error.')
                    return
            elif userObject.currentDirectory != '.':
                file = (os.getcwd() + os.path.join(userObject.currentDirectory, tokens[2])).replace('\\', '/')
                try:
                    f = open(file, "x")
                    self.printLog(userObject.user + ' created new file named ' + tokens[2] + ' in ' + userObject.currentDirectory)
                except:
                    clientSocket.sendall(b'500 Error.')
                    return

            msg = '257 ' + tokens[2] + ' created.'
            clientSocket.sendall(str.encode(msg))

    def handleRMD(self, tokens, clientSocket, userObject):
        # RMD -f <name>
        if tokens[1] == '-f':
            if userObject.currentDirectory == '.':
                directory = (os.path.join(os.getcwd(), tokens[2])).replace('\\', '/')
                if os.path.exists(directory):
                    shutil.rmtree(directory)
                    self.printLog(userObject.user + ' deleted directory named ' + tokens[2] + ' in ' + userObject.currentDirectory)
                else:
                    clientSocket.sendall(b'500 No such directory.')
                    return
            elif userObject.currentDirectory != '.':
                directory = (os.getcwd() + os.path.join(userObject.currentDirectory, tokens[2])).replace('\\', '/')
                if os.path.exists(directory):
                    shutil.rmtree(directory)
                    self.printLog(userObject.user + ' deleted directory named ' + tokens[2] + ' in ' + userObject.currentDirectory)
                else:
                    clientSocket.sendall(b'500 No such directory.')
                    return

            msg = '250 ' + tokens[2] + ' deleted.'
            clientSocket.sendall(str.encode(msg))

        # RMD <name>
        elif tokens[1] != '-f':
            if userObject.currentDirectory == '.':
                file = (os.path.join(os.getcwd(), tokens[1])).replace('\\', '/')
                if os.path.exists(file):
                    os.remove(file)
                    self.printLog(userObject.user + ' deleted file named ' + tokens[1] + ' in ' + userObject.currentDirectory)
                else:
                    clientSocket.sendall(b'500 No such file.')
                    return
            elif userObject.currentDirectory != '.':
                file = (os.getcwd() + os.path.join(userObject.currentDirectory, tokens[1])).replace('\\', '/')
                if os.path.exists(file):
                    os.remove(file)
                    self.printLog(userObject.user + ' deleted file named ' + tokens[1] + ' in ' + userObject.currentDirectory)
                else:
                    clientSocket.sendall(b'500 No such file.')
                    return

            msg = '250 ' + tokens[1] + ' deleted.'
            clientSocket.sendall(str.encode(msg))

    def handleLIST(self, tokens, clientSocket, userObject, clientDataSocket):
        files = []
        directories = []
        if userObject.currentDirectory == '.':
            for (dirpath, dirnames, filenames) in os.walk(os.getcwd()):
                files.extend(filenames)
                directories.extend(dirnames)
                break
        elif userObject.currentDirectory != '.':
            for (dirpath, dirnames, filenames) in os.walk(os.getcwd() + userObject.currentDirectory):
                files.extend(filenames)
                directories.extend(dirnames)
                break

        info = {'files': files, 'dirs' : directories}
        msg = '226 List transfer done.'
        ls = 'list '
        for dir in info['dirs']:
            ls += '[ dir] ' + dir + '\n'
        for file in info['files']:
            ls += '[file] ' + file + '\n'
        if ls == 'list ':
            ls = 'list <Directory is empty>'
        clientSocket.send(str.encode(msg))

        # Send data type [list] and content to data channel
        clientDataSocket.sendall(ls.encode())

    def handleCWD(self, tokens, clientSocket, userObject):
        # CDW <empty>
        if len(tokens) == 1:
            userObject.currentDirectory = '.'
            clientSocket.sendall(b'250 Successful Change.')

        # CWD ..
        elif tokens[1] == '..':
            if userObject.currentDirectory == '.' or userObject.currentDirectory == '/':
                clientSocket.sendall(b'500 Error.')
            else:
                path = pathlib.Path(userObject.currentDirectory)
                userObject.currentDirectory = str(path.parent).replace('\\', '/')
                clientSocket.sendall(b'250 Successful Change.')

        # CWD <path>
        else:
            if tokens[1] == '/':
                clientSocket.sendall(b'250 Successful Change.')
                return
            if userObject.currentDirectory == '.':
                path = '/' + tokens[1]
            else:
                path = userObject.currentDirectory + '/' + tokens[1]
            if os.path.isdir(os.getcwd() + path):
                userObject.currentDirectory = path
                clientSocket.sendall(b'250 Successful Change.')
            else:
                clientSocket.sendall(b'500 Error.')
    
    def handleDL(self, tokens, clientSocket, userObject, clientDataSocket):
        if len(tokens) != 2:
            clientSocket.sendall(b'501 Syntax error in parameters or arguments.')
            return
        fileName = tokens[1]
        if not os.path.isfile((os.getcwd() + os.path.join(userObject.currentDirectory, fileName)).replace('\\', '/')):
            clientSocket.sendall(b'550 File unavailable.')
            return
        if self.enableAuthorization:
            # Check if user has access to download the file
            if fileName in self.files:
                if userObject.isAdmin:
                    self.accountingManagement(fileName, clientSocket, userObject, clientDataSocket)
                else:
                    clientSocket.sendall(b'550 File unavailable.')
            else:
                self.accountingManagement(fileName, clientSocket, userObject, clientDataSocket)
        else:
            self.accountingManagement(fileName, clientSocket, userObject, clientDataSocket)

    def accountingManagement(self, fileName, clientSocket, userObject, clientDataSocket):
        if self.enableAccounting:
            fileSize = os.stat((os.getcwd() + os.path.join(userObject.currentDirectory, fileName)).replace('\\', '/')).st_size
            # Check if user has enough download traffic
            if userObject.size > fileSize:
                self.uploadOnSocket(fileName, clientSocket, userObject, clientDataSocket, fileSize)
            else:
                clientSocket.sendall(b"425 Can't open data connection.")
        else:
            self.uploadOnSocket(fileName, clientSocket, userObject, clientDataSocket, fileSize)

    def uploadOnSocket(self, fileName, clientSocket, userObject, clientDataSocket, fileSize):
        fileContent = open((os.getcwd() + os.path.join(userObject.currentDirectory, fileName)).replace('\\', '/'),encoding='latin-1').read()
        clientSocket.sendall(b'226 Successful Download.')

        # Send data type [file] and content to data channel
        fileContent = 'file ' + fileName + ' ' +  fileContent
        clientDataSocket.sendall(fileContent.encode())
        userObject.size -= fileSize

        log = ' downloaded ' + fileName + ' from ' + userObject.currentDirectory
        self.printLog(userObject.user + log)

        # Check if user has enough traffic
        if userObject.size < self.threshold and userObject.alert == True:
            self.sendMail(userObject)

    def handleHELP(self, tokens, clientSocket, userObject):
        clientSocket.sendall(str.encode(HELP_TEXT))
        
    def printLog(self, text):
        if self.enableLogging:
            if self.loggingPath != None:
                text = '[' + time.asctime() + '] ' + text + '\n'
                f = open(self.loggingPath, "a")
                f.write(text)
                f.close()

    def sendMail(self, userObject):
        username = "ali.jalali99"
        password = "AlijalalI99"
        CONTENT = "\r\n You don't have enough traffic :(" + "\r\n.\r\n"

        mailserver = ("mail.ut.ac.ir", 587) 
        mailSocket = socket(AF_INET, SOCK_STREAM)
        mailSocket.connect(mailserver)
        connect_receive = mailSocket.recv(1024)

        HELO = "HELO Ali\r\n"
        mailSocket.send(HELO.encode())
        HELO_receive = mailSocket.recv(1024)

        SENDER = "MAIL FROM:<ali.jalali99@ut.ac.ir>\r\n"
        mailSocket.send(SENDER.encode())
        SENDER_receive = mailSocket.recv(1024)

        AUTHENTICATION = "AUTH LOGIN\r\n"
        mailSocket.send(AUTHENTICATION.encode())
        AUTHENTICATION_receive = mailSocket.recv(1024)

        username = base64.b64encode((username+"\n").encode()) + "\r\n".encode()
        mailSocket.send(username)
        USER_receive = mailSocket.recv(1024)

        password = base64.b64encode((password).encode()) + "\r\n".encode()
        mailSocket.send(password)
        PASS_receive = mailSocket.recv(1024)
        
        RECEIVER = "RCPT TO:<%s>\r\n" %(userObject.email)
        # RECEIVER = "RCPT TO:<pouramini.majid@yahoo.com>\r\n"
        mailSocket.send(RECEIVER.encode())
        RECEIVER_receive = mailSocket.recv(1024)

        DATA = "DATA\r\n"
        mailSocket.send(DATA.encode())
        DATA_receive = mailSocket.recv(1024)

        mailSocket.send(CONTENT.encode())
        CONTENT_receive = mailSocket.recv(1024)

        FINISH = "QUIT\r\n"
        mailSocket.send(FINISH.encode())
        FINISH_receive = mailSocket.recv(1024)
        mailSocket.close()

configFile = open('config.json')
configData = json.load(configFile)
server = Server(configData)
server.run()