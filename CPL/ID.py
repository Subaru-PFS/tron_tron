#!/usr/bin/env python

__all__ = ['ID']

import threading

class ID(object):
    """ Provide a thread-safe counter.
    """
    
    def __init__(self, start=1):
        self.id = start
        self.lock = threading.Lock()
        
    def gimme(self):
        """ Return the next ID, and increment the internal counter. """

        self.lock.acquire()
        id = self.id
        self.id += 1
        self.lock.release()

        return id
