import new

class A(object):
    def __init__(self, **argv):
        self.buffer = argv.get('s', 'a default string')

    def setDecoder(self, d):
        self.decode = new.instancemethod(d, self, A)

    def decode(self):
        return "No decoder defined."

class D1(object):
    def __init__(self, buffer):
        self.buffer = buffer

    def setNub(self, n):
        self.nubID = n
        
    def decode(self):
        c0 = self.buffer[0]
        self.buffer = self.buffer[1:]
        return c0
    
def decode(self):
    if len(self.buffer) == 0:
        return None
    c0 = self.buffer[0]
    self.buffer = self.buffer[1:]
    return c0

a = A()
print a.decode()
a.setDecoder(decode)

while 1:
    c = a.decode()
    if c == None:
        break
    print "read %s" % (c)
