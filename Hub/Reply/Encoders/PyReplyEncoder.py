__all__ = ['PyReplyEncoder']
           
import cPickle

import CPL
from Hub.Reply.FullReply import FullReply
from ReplyEncoder import ReplyEncoder

class PyReplyEncoder(ReplyEncoder):
    """ Encode Replys as single-line pickled python objects.
    """
    
    def __init__(self, **argv):
        ReplyEncoder.__init__(self, **argv)
        
        # How do we terminate encoded lines?
        #
        self.EOL = argv.get('EOL', '\f')
        self.encode = self.encodeFull

    def encodeFull(self, r, nub, noKeys=False):
        """ Encode a reply for a given nub.
        
        Encode all the information required to track the source of the command and the reply.
        """

        fullReply = FullReply()
        fullReply.initFromReply(r, noKeys)
        fullPickle = cPickle.dumps(fullReply)

        if self.debug > 6:
            CPL.log('PyEncode.encode', 'encoding FullReply %s as %r' % (fullReply, fullPickle))
        elif self.debug > 3:
            CPL.log('PyEncode.encode', 'encoding FullReply %s' % (fullReply,))
        
        return "%s%s" % (fullPickle, self.EOL)
