__all__ = ['RawReplyDecoder']

import CPL
from ReplyDecoder import ReplyDecoder
from Parsing import parseRawReply

class RawReplyDecoder(ReplyDecoder):
    def __init__(self, **argv):
        ReplyDecoder.__init__(self, **argv)
        
        self.EOL = argv.get('EOL', '\n')
        self.stripChars = argv.get('stripChars', '')
        
    def decode(self, buf, newData):
        """ Find and extract a single complete reply in the buf. Uses .EOL to
            recognize the end of a reply. 

        Returns:
          - a Reply instance. None if .EOL no found in buf.
          - the content of buf with the first complete reply removed.

        Always consumes input up to the first .EOL, if .EOL is found.
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
            CPL.log('Stdin.extractReply', "hoping to parse %r" % (replyString))

        for c in self.stripChars:
            replyString = replyString.replace(c, '')

        r = parseRawReply(replyString)
        
        if self.debug > 3:
            CPL.log('RawReplyDecoder.extractReply', "extracted %r, returning %r" % (r, buf))

        return r, buf

