#!/usr/bin/env python

__all__ = ['PollConnect']

import socket

import IOHandler
import CPL

class PollConnect(IOHandler.IOHandler):
    """ Provide asynchronous socket accept() handling. """
    
    def __init__(self, poller, host, port, depth=5, callback=None):
        """ Set up to accept new connections on a given port.

        Args:
           poller      - the PollHandler instance to register with.
           host, port  - the host and port arguments to listen(2)
           depth       - the number of pending incoming connections to allow.
                         set to 0 to make the instance quit after one connection.
           callback    - the function to call as callback(fd, remote_addr) on new connections.

        """

        self.poller = poller
        self.depth = depth
        self.acceptMany = depth
        self.callback = callback
        if depth == 0:
            depth = 1
            
        self.listenFd = None
        try:
            self.listenFd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.listenFd.bind((host, port))
            self.listenFd.listen(depth)
        except:
            if self.listenFd:
                self.listenFd.close()
            raise
        
        self.poller.addInput(self)
        
    def __del__(self):
        self.poller.removeInput(self)
        self.listenFd.close()
        
    def getInputFile(self):
        return self.listenFd.fileno()

    def readInput(self):

        CPL.log("IOAccept.readInput", "accepting...")
        newfd, addr = self.listenFd.accept()

        # Listen for a single connect. Kill ourselves if we should.
        #
        if self.acceptMany == 0:
            self.poller.removeInput(self)
            self.poller = None
        self.listenFd.listen(self.depth)

        if self.callback:
            self.callback(newfd, addr)
