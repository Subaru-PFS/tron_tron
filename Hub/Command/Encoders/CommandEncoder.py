__all__ = ['CommandEncoder']
           
import CPL

class CommandEncoder(CPL.Object):
    def __init__(self, **argv):
        CPL.Object.__init__(self, **argv)
        
        self.name = argv.get('name', 'unnamed')
        self.nubID = None
        
    def setNub(self, n):
        self.nubID = n
        
    def setName(self, s):
        self.name = s
        
