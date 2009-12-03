__all__ = ['ASCIIReplyEncoder']
           
import re

import CPL
from Hub.KV.KVDict import kvAsASCII
from ReplyEncoder import ReplyEncoder

class ASCIIReplyEncoder(ReplyEncoder):
    """ Encode Replys in a basic ASCII protocol. """
    
    def __init__(self, **argv):
        ReplyEncoder.__init__(self, **argv)
        
        # How do we terminate encoded lines?
        #
        self.EOL = argv.get('EOL', '\n')

        # Do we encode the minimal info, or include full tracking info?
        #
        self.simple = argv.get('simple', True)
        if self.simple:
            self.encode = self.encodeSimple
        else:
            self.encode = self.encodeFull
            
        # And should the key source be included?
        #
        self.noSrc = argv.get('noSrc', False)
        
        self.CIDfirst = argv.get('CIDfirst', False)

    def encodeSimple(self, r, nub, noKeys=False):
        """ Encode a reply for a given nub.
        
        The simple encoding returns the minimum that a selfish ICC needs to know about --
        whether the reply is to one of its commands, and if so which one.
        """

        cmd = r.cmd
        cid = cmd.cmdrCid
        mid = cmd.cmdrMid

        # This is scary. For clients which do not identify their command sources, we want to return
        # their CID (0) unmolested but we need to name the client to other listeners.
        #
        if cid == '0' and self.nubID != cmd.cmdrName:
            cid = cmd.cmdrName
            
        if self.CIDfirst:
            id_s = "%s %s" % (cid, mid)
        else:
            id_s = "%s %s" % (mid, cid)

        if self.debug > 5:
            CPL.log('ASCIIReplyEncoder.encode', 'CIDfirst=%s, cid=%s, mid=%s, id_s=%s' % (self.CIDfirst, cid, mid, id_s))
        
        if noKeys:
            keys = ''
        else:
            keys = self.encodeKeys(r.src, r.KVs)
            
        if self.noSrc:
            return "%s %s %s%s" % (id_s, \
                                   r.flag, keys, self.EOL)
        else:
            return "%s %s %s %s%s" % (id_s, \
                                      r.src, r.flag, keys, self.EOL)

    def encodeFull(self, r, nub, noKeys=False):
        """ Encode a reply for a given nub.
        
        Encode all the information required to track the source of the command and the reply.
        """

        cmd = r.cmd

        if noKeys:
            keys = ''
        else:
            keys = self.encodeKeys(r.src, r.KVs)
            
        return "%s %s %s %s %s %s %s %s %s%s" % (cmd.cmdrName, cmd.cmdrMid, cmd.cmdrCid, 
                                                 cmd.actorName, cmd.actorMid, cmd.actorCid,
                                                 r.src, r.flag,
                                                 keys, self.EOL)
        
    def encodeKeys(self, src, KVs):
        """ Return a string encoding of KVs stored in an OrderedDict.

        Args:
           src   - ignored
           KVs   - an OrderedDict of values. See Parsing/parsing.py for important details.
        Notes:
        
        """
        
        if self.debug > 5:
            CPL.log("ASCIIReplyEnc.encode", "encoding %r" % (KVs,))
        if KVs == None:
            return ""
        
        keylist = []
        for k, v in KVs.iteritems():
            if self.debug > 5:
                CPL.log("ASCIIReplyEnc.encode", "encoding %r=%r" % (k, v))

            keylist.append(kvAsASCII(k, v, escape=self.EOL))
            
        return "; ".join(keylist)
    

if __name__ == "__main__":
    import sys
    
    tests = ('Received="26437.910 00010000   14.6028678 -10.32"   0"',
             "distxt=\"Unrecognized command: '\"'\"",
             "",
             'e="',
             "e='",
             'abc = "oh no", "please no", 1',
             "d=99.9", "e=99,9",
             "k=a,'b'",
             "z29=   abc;  def",
             'k9="sddsas'
             )
    sys.stderr.write('\n\n')
    for t in tests:
        sys.stderr.write("====== :%s:\n" % (t))
        d = parseKVs(t)
        print "t=:%s: d=%s" % (t, d)
        
    
