__all__ = ['SocketActorNub']

import socket

from ActorNub import ActorNub

class SocketActorNub(ActorNub):
    def __init__(self, poller, host, port, **argv):
        """ 
        """
        
        ActorNub.__init__(self, poller, **argv)
        self.host = host
        self.port = port
        
        f = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        f.connect((host, port))
        f.setblocking(0)
        
        self.setInputFile(f)
        self.setOutputFile(f)

        self.connected()
