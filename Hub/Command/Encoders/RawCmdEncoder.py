__all__ = ['RawCmdEncoder']
           
import CPL
from CommandEncoder import CommandEncoder

class RawCmdEncoder(CommandEncoder):
    """ Encode commands into a raw ASCII protocol: one without any MID, CID, etc.
    
    Options:
        EOL:       specify the EOL string. Default is '\n'
    """
    
    def __init__(self, **argv):
        CommandEncoder.__init__(self, **argv)

        self.EOL = argv.get('EOL','\n')
        
    def encode(self, cmd):

        e = "%s%s" % (cmd.cmd, self.EOL)
        if self.debug > 5:
            CPL.log("RawEncoder", "encoded: %s" % (e))

        return e
    
