__all__ = ['ASCIICmdDecoder']

import re

import CPL
from Hub.Command import Command
import g

import CommandDecoder

class ASCIICmdDecoder(CommandDecoder.CommandDecoder):

    # REs to match commands like:
    #   cmdrName TGT command
    #
    mctc_re = re.compile(r"""
      \s*
      (?P<cid>[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*)
      \s+
      (?P<mid>[0-9]+)
      \s+
      (?P<tgt>[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*)
      \s+
      (?P<cmd>.*)""",
                         re.IGNORECASE | re.VERBOSE)

    #   MID TGT command
    #
    mtc_re = re.compile(r"""
      \s*
      (?P<mid>[0-9]+)
      \s+
      (?P<tgt>[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*)
      \s+
      (?P<cmd>.*)""",
                        re.IGNORECASE | re.VERBOSE)
    #   TGT command
    #
    tc_re = re.compile(r"""
      \s*
      (?P<tgt>[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*)
      \s+
      (?P<cmd>.*)""",
                       re.IGNORECASE | re.VERBOSE)

    def __init__(self, **argv):

        CommandDecoder.CommandDecoder.__init__(self, **argv)
        
        self.EOL = argv.get('EOL', '\n')
        self.needCID = argv.get('needCID', True)
        self.needMID = argv.get('needMID', True)
        self.hackEOL = argv.get('hackEOL', False)
        
        if self.needCID and not self.needMID:
            CPL.log("ASCIICmdDecoder", "if CID is needed, than MID must also be.")
        if self.needMID == False:
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

        # Telnet connections provide '\r\n'. Or worse, I fear.
        if self.hackEOL and len(buf) > 0:
            if buf[eol-1] == '\r':
                self.EOL = '\r' + self.EOL
                self.hackEOL = False
                eol = buf.find(self.EOL)
                CPL.log('ASCIICmdDecoder.decode', "adjusted EOL to %r (at %d) in: %r" % (self.EOL, eol, buf))
                g.hubcmd.warn('Text=%s' % \
                              CPL.qstr("adjusted EOL for %s to %r (at %d) in: %r" % (self.name, self.EOL, eol, buf)),
                              src='hub')
                if eol == -1:
                    return None, buf
               
        cmdString = buf[:eol]
        buf = buf[eol+len(self.EOL):]

        if self.needCID:
            match = self.mctc_re.match(cmdString)
            if match == None:
                g.hubcmd.fail('ParseError=%s' % \
                              (CPL.qstr('xxx Command from %s could not be parsed: %r' % \
                                        (self.name, cmdString))),
                              src='hub')
                return None, buf
            d = match.groupdict()
        elif self.needMID:
            match = self.mtc_re.match(cmdString)
            if match == None:
                g.hubcmd.fail('ParseError=%s' % \
                              (CPL.qstr('Command from %s could not be parsed: %r' % \
                                        (self.name, cmdString))),
                              src='hub')
                return None, buf
            d = match.groupdict()
            d['cid'] = self.name
        else:
            match = self.tc_re.match(cmdString)

            mid = self.mid
            self.mid += 1

            if match == None:
                g.hubcmd.fail('ParseError' % \
                              (CPL.qstr('Command from %s could not be parsed: %r' % \
                                       (self.name, cmdString))),
                              src='hub')
                return None, buf
            else:
                d = match.groupdict()
                d['cid'] = self.name
                d['mid'] = str(mid)

        return Command(self.nubID, d['cid'], d['mid'], d['tgt'], d['cmd']), buf
