__all__ = ['FullReply']

from RO.Alg import OrderedDict

class FullReply(object):
    """ A single object containing all known information about a single reply. Basically flattens
    a Reply and its Command into a single structure.
    
    cmdrName
    cmdrMid
    cmdrCid
    
    actorName
    actorMid
    actorCid
    
    src               - who generated the flag and KVs. Usually actorName, but not always.
    flag
    KVs
    """

    def __str__(self):
        return "FullReply(cmdrName=%s, cmdrMid=%s, cmdrCid=%s, actorName=%s, actorMid=%s, actorCid=%s, src=%s, flag=%s, KVs=%s)" \
               % (self.cmdrName, self.cmdrMid, self.cmdrCid,
                  self.actorName, self.actorMid, self.actorCid,
                  self.src, self.flag, self.KVs)


    def initFromReply(self, r, noKeys=False):
        
        cmd = r.cmd

        self.cmdrName = cmd.cmdrName
        self.cmdrMid = cmd.cmdrMid
        self.cmdrCid = cmd.cmdrCid
        
        self.actorName = cmd.actorName
        self.actorMid = cmd.actorMid
        self.actorCid = cmd.actorCid
        
        self.src = r.src
        self.flag = r.flag

        if noKeys:
            self.KVs = OrderedDict()
        else:
            self.KVs = r.KVs
        
        
