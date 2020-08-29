class User:
    def __init__(self, user, password, size=None, email=None, alert=False, isAdmin=False, isLoggedin=False, currentDirectory='', requestedForLogin=False):
        self.user = user
        self.password = password
        self.size = size
        self.email = email
        self.alert = alert
        self.isAdmin = isAdmin
        self.isLoggedin = isLoggedin
        self.currentDirectory = currentDirectory
        self.requestedForLogin = requestedForLogin