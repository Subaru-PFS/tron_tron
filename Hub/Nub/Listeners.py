__all__ = ['SocketListener']

import CPL

import IO
import hub

class SocketListener(object):
    """ Wait for connections on a given TCP port.
    """
    
    def __init__(self, poller, port, name, callback):

        self.name = name
        self.port = port
        self.poller = poller
        self.ID = self.name
        self.callback = callback
        self.listener = IO.PollAccept(poller, '', port, callback=self.acceptOne)    

    def __del__(self):
        self.listener = None

    def shutdown(self, notifyHub=True, why=""):
        """ Release all resources and shut down. 

        If called from "below" (i.e. a socket has been shutdown), just
        calls the hub's dropNub method, which will shortly call us back.
        
        If called from the hub, close all IO resources.
        """
        
        CPL.log("Hub.shutdown", "notify=%s why=%s" % (notifyHub, why))
        
        if notifyHub:
            hub.dropNub(self)
        else:
            self.listener.shutdown()
            del self.listener

    def acceptOne(self, f, addr):
        f.setblocking(0)
        self.callback(f, f, addr)

