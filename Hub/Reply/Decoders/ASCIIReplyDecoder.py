__all__ = ['ASCIIReplyDecoder']

import g
import CPL
from Parsing import *
from ReplyDecoder import ReplyDecoder

class ASCIIReplyDecoder(ReplyDecoder):
    def __init__(self, **argv):
        ReplyDecoder.__init__(self, **argv)
        
        self.EOL = argv.get('EOL', '\n')
        self.cidFirst = argv.get('CIDfirst', True)
        self.stripChars = argv.get('stripChars', '')
        
    def decode(self, buf, newData):
        """ Find and extract a single complete reply in the buf. Uses .EOL to
            recognize the end of a reply. 

        Returns:
          - a Reply instance. None if .EOL no found in buf.
          - the content of buf with the first complete reply removed.

        Always consumes input up to the first .EOL, if .EOL is found.
        If .EOL is found, but the input can not be properly parsed, a modified reply is generated:

          - If no header information is found (i.e. no MID, CID, etc), the following is returned:
              w RawInput="full line"
          - If header information is found, but some part of the keywords are not parseable,
              x K1=V1; K2; RawKeys="rest of line"
          - If header information is found, and the last valueis an unterminated string, that
              value is silently terminated.
        """

        if newData:
            buf += newData
        
        if self.debug > 5:
            CPL.log('Stdin.extractReply', "called with EOL=%r and buf=%r" % (self.EOL, buf))

        eol = buf.find(self.EOL)
        if self.debug > 4:
            CPL.log('Stdin.extractReply', "eol at %d in buffer %r" % (eol, buf))

        # No complete reply found. make sure to return
        # the unmolested buffer.
        #
        if eol == -1:
            return None, buf

        replyString = buf[:eol]
        buf = buf[eol+len(self.EOL):]

        if self.debug > 2:
            CPL.log('Stdin.extractReply', "hoping to parse (CIDfirst=%s) %r" % (self.cidFirst, replyString))

        for c in self.stripChars:
            replyString = replyString.replace(c, '')
            
        # Make sure to consume unparseable junk up to the next EOL.
        #
        try:
            r = parseASCIIReply(replyString, cidFirst=self.cidFirst)
        except SyntaxError, e:
            CPL.log("ASCIIReplyDecoder", "Parsing error from %s: %r" % (self.name, e))
            return None, buf
        
        if self.debug > 3:
            CPL.log('Stdin.extractReply', "extracted %r, returning %r" % (r, buf))

        return r, buf

