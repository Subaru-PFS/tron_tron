__all__ = ['SocketCommanderNub']

import socket

from Commanders import CommanderNub

class SocketCommanderNub(CommanderNub):
    def __init__(self, poller, host, port, **argv):
        """ 
        """
        
        CommanderNub.__init__(self, poller, **argv)
        self.host = host
        self.port = port
        
        f = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        f.connect((host, port))
        f.setblocking(0)
        
        self.setInputFile(f)
        self.setOutputFile(f)

        self.connected()
