__all__ = ['CommandEncoder',
           'BinaryCmdEncoder',
           'ASCIICmdEncoder']
           
import struct

import CPL
from Command import Command

class CommandEncoder(CPL.Object):
    def __init__(self, **argv):
        CPL.Object.__init__(self, **argv)
        
        self.name = argv.get('name', 'unnamed')
        self.nubID = None
        
    def setNub(self, n):
        self.nubID = n
        
    def setName(self, s):
        self.name = s
        
class BinaryCmdEncoder(CommandEncoder):
    def __init__(self, **argv):
        CommandEncoder.__init__(self, **argv)

    def encode(self, cmd):
        """ Encapsulate an old-style binary command.  """
        
        str = cmd.cmd
        length = len(str)
        csum = 0
        for i in xrange(length):
            csum ^= ord(str[i])

        # See extractCompleteCommand for better notes.
        #
        packet = struct.pack('>BBihh%dsBB' % (length), 1, 1,
                             length, cmd.actorMid, cmd.actorCid, str, csum, 4)

        if self.debug > 3:
            CPL.log('BinaryCmdEncoder', "cmd=%s data=%r" % (cmd, packet))

        return packet

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
    
