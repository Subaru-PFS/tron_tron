__all__ = ['tcmd']

class tcmd(object):
    def __init__(self, name='tcmd'):
        self.name = name
        
    def inform(self, *args):
        print "%s.inform: %s" % (self.name, ''.join(*args))

    def warn(self, *args):
        print "%s.warn: %s" % (self.name, ''.join(*args))

    def fail(self, *args):
        print "%s.fail: %s" % (self.name, ''.join(*args))
            
