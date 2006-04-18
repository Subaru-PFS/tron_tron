__all__ = ['Object']

import sys

class Object(object):
    """ Provide a convenient place to add "global" hooks. Currently only grabs a debug=N argument.
    
    """
    
    def __init__(self, **argv):
        object.__init__(self)
        self.debug = argv.get('debug', 0)
 
        if self.debug > 5:
            sys.stderr.write("init %r\n" % (self))

    def __del__(self):
        if self.debug > 5:
            try:
                sys.stderr.write("del %r\n" % (self))
            except:
                pass
