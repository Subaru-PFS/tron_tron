class FullReply(object):
    """ A single object containing all known information about a single reply.
    
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
        """ This is an unusual __str__ routine, in that it often provides the primary output
            on the command line. So we let a global describe how we want to format the output.

            replayFormat = ('debug', 'full', 'simple', 'warnings', 'quiet')
                full     - print everything
                simple   - print the src, the flag, the MID and the keys.
                warnings - only print warnings and errors.
                quiet    - print nothing.
        """

        level = 'simple'

        if level == 'debug':
            return "FullReply(cmdrName=%s, cmdrMid=%s, cmdrCid=%s, actorName=%s, actorMid=%s, actorCid=%s, src=%s, flag=%s, KVs=%s)" \
                   % (self.cmdrName, self.cmdrMid, self.cmdrCid,
                      self.actorName, self.actorMid, self.actorCid,
                      self.src, self.flag, self.KVs)
        elif level == 'simple':
            return "%s %s %s" % (flag, src, self.prettyKVs())

    def prettyKVs(self):
        """ Return a human-friendly version of the reply. """
        
        keys = "; ".join([prettyKey(k,v) for k,v in self.KVs.iteritems()])
        return keys
        

    def pretty(self, full=False):
        """ Return a human-friendly version of the reply. """
        
        keys = "; ".join([prettyKey(k,v) for k,v in self.KVs.iteritems()])
        return keys
    
    def prettyKey(self, k, v):
        """ """
        
        return "%s=%s" % (k, v)
    
    def initFromReply(self, r):
        
        cmd = r.cmd

        self.cmdrName = cmd.cmdrName
        self.cmdrMid = cmd.cmdrMid
        self.cmdrCid = cmd.cmdrCid
        
        self.actorName = cmd.actorName
        self.actorMid = cmd.actorMid
        self.actorCid = cmd.actorCid
        
        self.src = r.src
        self.flag = r.flag
        self.KVs = r.KVs
        
        
