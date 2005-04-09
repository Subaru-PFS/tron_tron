__all__ = ['Reply']

import time

from RO.Alg import OrderedDict
import CPL
import Parsing

"""
   Reply is a slight misnomer --

   - Reply to an existing command. Need to specify:
       - flag, cmd, [src], KVs
   - Generate non-command KVs. Need to specify:
       - flag, actorCid, actorMid, src, KVs
"""

class Reply(CPL.Object):
    
    def __init__(self, cmd, flag, KVs, bcast=True, **argv):
        """ Create a parsed Reply.

        Args:
           cmd  - the Command which we are a Reply to.
           flag - the completion state flag.
           KVs  - parsed or unparsed keys. We accept OrderedDicts, lists&tuples, and strings. The
                  latter are parsed into OrderedDicts.
        """

        CPL.Object.__init__(self, **argv)
        
        self.ctime = time.time()
        self.cmd = cmd
        self.flag = flag
        self.bcast = bcast
        
        if isinstance(KVs, OrderedDict):
            self.KVs = KVs
        else:
            self.KVs = self.parseKVs(KVs)
                
        self.src = argv.get('src', cmd.actorName)

    def finishesCommand(self):
        """ Return true if the given flag finishes a command. """

        return self.flag in ':fF'

    def __str__(self):
        return "Reply(cmd=%s flag=%s KVs=%s)" % (self.cmd, self.flag, self.KVs)
    
    def parseKVs(self, kvl):
        """ Convert some form of keys to an OrderedDict.

        We are trying to be ridiculously flexible here. Take:

         - a string, which we parse as it came from an ICC.
         - a list, which we parse either as a list of key=value strings or of (key, value) duples.
        """
        
        if type(kvl) == str:
            return Parsing.parseKVs(kvl)

        od = OrderedDict()
        if kvl != None:
            for i in kvl:
                if type(i) == str:
                    k, v, junk = Parsing.parseKV(i)
                    od[k] = v
                elif type(i) in (list, tuple) and len(i) == 2:
                    k, v, junk = Parsing.parseKV("%s=%s" % i)
                else:
                    CPL.log('Reply', 'kvl item is not a string: %r' % (i))
                    raise Exception("kvl == %r" % (i))

        return od
