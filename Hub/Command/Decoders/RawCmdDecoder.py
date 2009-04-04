__all__ = ['RawCmdDecoder']

import CPL
from Hub.Command import Command

import CommandDecoder

class RawCmdDecoder(CommandDecoder.CommandDecoder):
    """ A Command decoder for accepting commands which have no target, MID, or CID. We
    know our target, and assign an incrementing MID. In other words, we transform:

       cmdTxt -> tgt mid cmdTxt

    """
    
    def __init__(self, target, **argv):
        """ Create ourself.

        Args:
           target   - the name of an Actor.
        Optargs:
           EOL      - the EOL string (default='\n')
        """
        CommandDecoder.CommandDecoder.__init__(self, **argv)
        
        self.target = target
        self.EOL = argv.get('EOL', '\n')
        self.CID = argv.get('CID', '0')
        self.stripChars = argv.get('stripChars', '')
        self.mid = 1

    def decode(self, buf, newData):
        """ Find and extract a single complete command from the given buffer. 

        Returns:
           - a Command instance, or None if no complete command was found.
           - the unconsumed part of the buffer.

           If a command-sized piece is found, but cannot be parsed,
           return None, leftovers.
           
        """
        
        if newData:
            buf += newData
        
        eol = buf.find(self.EOL)
        
        if self.debug > 2:
            CPL.log('ASCIICmdDecoder.extractCmd', "EOL at %d in buffer %r" % (eol, buf))

        # No complete command found. Return the original buffer so that the caller
        # can easily determine that no input was consumed.
        #
        if eol == -1:
            return None, buf

        # We have a complete command. Strip it off from the rest of the input buffer.
        #
        cmdString = buf[:eol]
        buf = buf[eol+len(self.EOL):]

        for c in self.stripChars:
            cmdString.replace(c, '')
            
        # Assign a new MID
        #
        mid = self.mid
        self.mid += 1
        
        return Command(self.nubID, self.CID, mid, self.target, cmdString), buf
