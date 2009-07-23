__all__ = ['ReplyEncoder']
           
import CPL

class ReplyEncoder(CPL.Object):

    def __init__(self, **argv):
        CPL.Object.__init__(self, **argv)

        self.name = argv.get('name', '.unnamed')
        self.nubID = None
        
    def setNub(self, n):
        self.nubID = n
        
    def setName(self, s):
        self.name = s

    def encode(self, s):
         RuntimeError(".encode() must be defined in a ReplyEncoder subclass.")
        
