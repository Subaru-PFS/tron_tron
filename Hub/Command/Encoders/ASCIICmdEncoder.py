__all__ = ['ASCIICmdEncoder']
           
import CPL
from CommandEncoder import CommandEncoder

class ASCIICmdEncoder(CommandEncoder):
    """ Encode commands into the simple ASCII protocol.
    
    Options:
        EOL:       specify the EOL string. Default is '\n'
        useCID:    whether we can meaningfully specify the CID. Uses
                   0 for the CID if False. Default is True.
        useTarget: whether the name of the Actor should be included. Default is False.
    """
    
    def __init__(self, **argv):
        CommandEncoder.__init__(self, **argv)
        self.EOL = argv.get('EOL','\n')
        self.useCID = argv.get('useCID', True)
        self.useTarget = argv.get('useTarget', False)
        self.sendCmdr = argv.get('sendCommander', False)
        
    def encode(self, cmd):
        if self.useCID:
            ids = "%s %s " % (cmd.actorMid, cmd.actorCid)
        else:
            ids = "%s 0 " % (cmd.actorMid,)

        if self.sendCmdr:
            cmdrInfo = "%s " % (cmd.cmdrName)
        else:
            cmdrInfo = ""
            
        if self.useTarget:    
            e = "%s%s %s%s%s" % (cmdrInfo, cmd.actorName, ids, cmd.cmd, self.EOL)
        else:
            e = "%s%s%s%s" % (cmdrInfo, ids, cmd.cmd, self.EOL)

        if self.debug > 5:
            CPL.log("ASCIIEncoder", "encoded: %s" % (e))

        return e
    
