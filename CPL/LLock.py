__all__ = ['LLock']

from threading import Lock

import CPL

class LLock(object):
    """ Debugging Lock. Can print when the acquire & release calls are made. """
    seq = 1
    
    def __init__(self, debug=0, name=None):
        self.debug = debug
        self.lock = Lock()
        if name == None:
            name = 'lock-%04d' % (seq)
            seq += 1
        self.name = name
        
        if self.debug > 0:
            CPL.log("LLock.create", "name=%s" % (self.name))
        
    def acquire(self, block=True, src="up"):
        if self.debug > 0:
            CPL.log("LLock.acquire", "name=%s, block=%s, src=%s" % \
                    (self.name, block, src))
        self.lock.acquire(block)
        
    def release(self, src="up"):
        if self.debug > 0:
            CPL.log("LLock.release", "name=%s, src=%s" % \
                    (self.name, src))
        self.lock.release()
        
