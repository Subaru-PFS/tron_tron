__all__ = ['BaseFilter',
           'ClientCmdFilter',
           'ClientFilter']

class BaseFilter(object):
    """ Wrap a Queue with a filter. """

    def __init__(self, q):
        """
        Args:
            q     - the Queue to send accepted responses to.
        """
        
        self.q = q

    def copeWithInput(self, x):
        """ Accept all input. """

        self.q.put(x)
        
class ClientCmdFilter(BaseFilter):
    """ Filter for command output. """

    def __init__(self, q, cid, mid):
        ClientFilter.__init__(self, q)

        self.cid = cid
        self.mid = mid

    def copeWithInput(self, reply):
        """ Accept replies to our command. """

        if reply.cmdrCid == self.cid and reply.cmdrMid == self.mid:
            self.q.put(reply)
            
class ClientFilter(BaseFilter):
    """ Filter on reply sources and on key names.
    """
    
    def __init__(self, q, actors=None, keys=None):
        BaseFilter.__init__(q)

        self.setActors(actors)
        self.setKeys(keys)

    def listify(self, x):
        """ Turn x into a list, by the following rules:

        If x is:
           None       -> []
           a tuple    -> list(x)
           a list     -> x
           otherwise  -> [x]
        
        """

        if x == None:
            return []
        if type(x) == type([]):
            return x
        if type(x) == type(()):
            return list(x)
        return [x]
    
    def setActors(self, actors):
        """ Unconditionally set the list of actors whose entire output we accept.

        Args:
           actors   - a list of actor names.

        If actors is not a list of strings, raises TypeError
        """

        actors = self.listify(actors)

        # Sanity check actors list.
        for a in actors:
            if type(a) != type(''):
                raise TypeError("actor %r is not a string" % (a))
            
        self.actors = actors

    def setKeys(self, keys):
        """ Unconditionally set the list of keys whose entire output we accept.

        Args:
           keys   - a list of (actor, keyname) pairs.
        """

        keys = listify(keys)

        # Sanity check input types.
        for k in keys:
            if type(k) != type(()) or len(k) != 2:
                raise TypeError("key specification is not an (actor, keyname) tuple: %r" % (k))

            tgt, key = k
            if type(tgt) != type(''):
                raise TypeError("target %r is not a string" % (tgt))
            if type(key) != type(''):
                raise TypeError("key %r is not a string" % (tgt))

        self.keys = keys
        
    def copeWithInput(self, reply):
        """ Accept a reply if if comes from the right actor or if it is a key we want. """

        if reply.src in self.actors:
            self.q.put(reply)
            return

        for i in reply.KVs.iteritems():
            if i in self.keys:
                self.q.put(reply)
                return
