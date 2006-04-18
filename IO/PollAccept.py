#!/usr/bin/env python

__all__ = ['PollAccept']

import socket

import CPL
import IOHandler

class PollAccept(IOHandler.IOHandler):
    """ Provide asynchronous socket accept() handling. """
    
    def __init__(self, poller, host, port, depth=5, callback=None, **argv):
        """ Set up to accept new connections on a given port.

        Args:
           poller      - the PollHandler instance to register with.
           host, port  - the host and port arguments to listen(2)
           depth       - the number of pending incoming connections to allow.
                         set to 0 to make the instance quit after one connection.
           callback    - the function to call as callback(fd, remote_addr) on new connections.

        """

        self.depth = depth
        self.host = host
        self.port = port
        
        IOHandler.IOHandler.__init__(self, poller, **argv)
        
        self.acceptMany = depth
        self.callback = callback
        if depth == 0:
            depth = 1
            
        self.listenFd = None
        try:
            self.listenFd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.listenFd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.listenFd.bind((host, port))
            self.listenFd.listen(depth)
        except:
            if self.listenFd:
                self.listenFd.close()
            raise
        
        self.poller.addInput(self)
        
    def __str__(self):
        return "PollAccept(host=%s port=%s depth=%s)" % (self.host, self.port, self.depth)
    
    def shutdown(self, **argv):
        CPL.log("PollAccept.shutdown", "shutting down %s" % (self))

        self.poller.removeInput(self)
        self.listenFd.close()
        
    def getInputFd(self):
        return self.listenFd.fileno()

    def readInput(self):

        CPL.log("IOAccept.readInput", "accepting...")
        newfd, addr = self.listenFd.accept()

        # Listen for a single connect. Kill ourselves if we should.
        #
        if self.acceptMany == 0:
            self.shutdown()

            #        else:
            #            self.listenFd.listen(self.depth)

        if self.callback:
            self.callback(newfd, addr)
