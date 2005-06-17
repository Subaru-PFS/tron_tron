__all__ = ['BaseFilter',
           'ClientCmdFilter',
           'ActorFilter',
           'ClientFilter']
           
import Queue

import CPL
import Command

class BaseFilter(Queue.Queue):
    """ Wrap a Queue with a filter. """

    def __init__(self, **argv):
        """
        Args:
            q     - the Queue to send accepted responses to.
        """

        Queue.Queue.__init__(self)
        
        self.debug = argv.get('debug', 0)
        
    def __str__(self):
        return "BaseFilter(debug=%d, id=%d)" % (self.debug, id(self))
    
    def copeWithInput(self, x):
        """ Accept all input. """

        self.put(x)
        
class ClientCmdFilter(BaseFilter):
    """ Filter for command output. Accepts all Replies to a given command. """

    def __init__(self, command, **argv):
        BaseFilter.__init__(self, **argv)

        self.cid = str(command.cmdrCid)
        self.mid = str(command.cmdrMid)

        CPL.log('Filters', 'created %s' % (self))
        
    def __str__(self):
        return "ClientCmdFilter(cid=%s, mid=%s, debug=%s, id=%s)" % \
               (self.cid, self.mid, self.debug, id(self))
    
    def copeWithInput(self, reply):
        """ Accept replies to our command. """

        if self.debug > 4:
            CPL.log('ClientCmdFilter', 'cid=%r, mid=%r, input: %s' % (self.cid, self.mid, reply))
    
        if reply.cmdrCid == self.cid and reply.cmdrMid == self.mid:
            if self.debug > 5:
                CPL.log('ClientCmdFilter', 'yes, qsize=%d' % (self.qsize()))
            self.put(reply)
        else:
            if self.debug > 5:
                CPL.log('ClientCmdFilter', 'no, qsize=%d t1=%s t2=%s cids=%r,%r, mids=%r,%r' \
                        % (self.qsize(),
                           reply.cmdrCid == self.cid,
                           reply.cmdrMid == self.mid,
                           reply.cmdrCid, self.cid,
                           reply.cmdrMid, self.mid))

class ActorFilter(BaseFilter):
    """ Filter for Actors: accepts remote commands, plus replies to commands we have sent. """

    def __init__(self, name, **argv):
        BaseFilter.__init__(self, **argv)
        
        self.name = name
        self.cmds = {}

        CPL.log('Filters', 'created %s' % (self))

    def __str__(self):
        return "ActorFilter(name=%s, cmds=%s, debug=%d, id=%d)" % \
               (self.name, self.cmds, self.debug, id(self))
    
    def addCommand(self, command, **argv):
        key = (str(command.cmdrCid), str(command.cmdrMid))
        self.cmds[key] = True

    def removeCommand(self, command, **argv):
        key = (str(command.cmdrCid), str(command.cmdrMid))
        del self.cmds[key]
        
    def copeWithInput(self, obj):
        """ Accept replies to our command and to any commands we have sent. """

        if self.debug > 5:
            CPL.log('ActorFilter', 'obj=%s' % (obj))

        # Accept incoming commands.
        if type(obj) == Command.Command:
            self.put(obj)
            return

        # Accept replies to our commands.
        reply = obj
        key = (str(reply.cmdrCid), str(reply.cmdrMid))
        if key in self.cmds:
            if self.debug > 5:
                CPL.log('ActorFilter', 'yes, qsize=%d, key=%s cmds=%s' % \
                        (self.qsize(),
                         key, self.cmds.keys()))
            self.put(obj)
        else:
            if self.debug > 5:
                CPL.log('ActorFilter', 'no, qsize=%d, key=%s cmds=%s' % \
                        (self.qsize(),
                         key, self.cmds.keys()))

class ClientFilter(BaseFilter):
    """ Filter on reply sources and on key names.
    """
    
    def __init__(self, src, keys=None, **argv):
        BaseFilter.__init__(self, **argv)

        self.setSrc(src)
        self.setKeys(keys)

    def __str__(self):
        return "ClientFilter(src=%s, keys=%s, debug=%d, id=%d)" % \
               (self.src, self.keys, self.debug, id(self))
    
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
    
    def tuplefy(self, x):
        """ Turn x into a tuple, by the following rules:

        If x is:
           None       -> ()
           a tuple    -> x
           a list     -> tuple(x)
           otherwise  -> (x)
        
        """

        if x == None:
            return ()
        if type(x) == type(()):
            return x
        if type(x) == type([]):
            return tuple(x)
        return (x,)
    
    def setSrc(self, src):
        """ Unconditionally set the source whose entire output we accept.

        Args:
           src   - an actor name.

        If actors is not a string, raises TypeError
        """

        if type(src) != type(''):
            raise TypeError("actor %r is not a string" % (src))
            
        self.src = src

    def setKeys(self, keys):
        """ Unconditionally set the list of keys we accept.

        Args:
           keys   - a list of (actor, keyname) pairs.
        """

        keys = self.tuplefy(keys)

        # Sanity check input types.
        for k in keys:
            if type(k) != type(''):
                raise TypeError("key specification is not an string: %r" % (k))

        self.keys = keys
        
    def copeWithInput(self, reply):
        """ Accept a reply if if comes from the right actor or if it is a key we want. """

        if self.debug > 6:
            CPL.log("ClientFilter", "src=%s keys=%s tasting src=%s keys=%s" % \
                    (self.src, self.keys, reply.src, reply.KVs.keys()))
            
        if reply.src != self.src:
            return

        if not self.keys:
            self.put(reply)
            return
        
        for k in reply.KVs.iterkeys():
            if k in self.keys:
                self.put(reply)
                return


if __name__ == "__main__":
    from FullReply import FullReply
    
    q = ClientCmdFilter(12, 13)
    
    r1 = FullReply()
    r2 = FullReply()
    
    r1.cmdrCid = 11
    r1.cmdrMid = 12
    r1.cmdr = "me"
    
    r2.cmdrCid = 12
    r2.cmdrMid = 13
    r2.cmdr = "me"
    r2.flag = 'i'
    
    q.copeWithInput(r1)
    q.copeWithInput(r2)
    
    while 1:
        r = q.get()
        print r
        
    
