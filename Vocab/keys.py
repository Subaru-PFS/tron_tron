__all__ = ['keys']

import time
import os

import CPL
from Hub.KV.KVDict import *
from Vocab.InternalCmd import *
import g
import hub

class keys(InternalCmd):
    """ All the commands that the "keys" package provides.
        To wit:

        keys getFor=actor K1 [K2 [K3 ...]]

        Keywords returned:
           The requested keywords. But the src of the keywords is keys.actor instead of the actual actor.
           
    """
    
    def __init__(self, **argv):
        InternalCmd.__init__(self, 'keys', **argv)

        self.commands = {'getFor': self.getFor}


    def getFor(self, cmd, finish=True):
        """ Fetch keywords for a given actor

        Usage:
           getFor=actor K1 [K2 ... ]
        """

        matched, unmatched, leftovers = cmd.match([('getFor', str)])
        
        try:
            actor = matched['getFor']
        except KeyError:
            cmd.fail('keysTxt="no actor specified"')
            return

        try:
            g.KVs.sources[actor]
        except KeyError:
            cmd.fail('keysTxt="actor %s is not connected"' % (actor))
            return

        keys = leftovers.keys()
        CPL.log("keys.getFor", "matched=%s; unmatched=%s; leftovers=%s" % (matched, unmatched, leftovers))
        
        matchedKeys, unmatchedKeys = g.KVs.getValues(actor, keys)
        if unmatchedKeys:
            failed = [CPL.qstr(x) for x in unmatchedKeys]
            cmd.warn('unmatchedKeys=%s' % (','.join(failed)), bcast=False)

        values = []
        for k, v in matchedKeys.iteritems():
            values.append(kvAsASCII(k, v))

        if values:
            cmd.inform("; ".join(values), noRegister=True, src="keys.%s" % (actor), bcast=False)
        if finish:
            cmd.finish()
        
def _test():
    a = auth()
    a.statusCmd
    
if __name__ == "__main__":
    _test()
    
    
