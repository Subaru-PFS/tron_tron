__all__ = ['InstExposure']

import CPL
import Actor
import ExpPath

class InstExposure(Actor.Actor):
    def __init__(self, name, **argv):
        Actor.Actor.__init__(self, name, debug=1)

        # The single active sequence.
        self.sequence = None

        # For status requests, keep the last sequence around.
        self.lastSequence = None
        
        self.paths = {}

    def status(self, cmd):
        """ Return status keyword describing the state of any existing sequence.
        """

        CPL.log('status', "starting status")

        seq = self.sequence
        if not seq:
            seq = self.lastSequence
            
        if seq != None:
            CPL.log('status', "status on %r" % (self.instName))
            seqState, expstate = seq.getKeys()
            # report back to caller the state
            cmd.respond("%s; %s" % (seqState, expstate))

        cmd.finish('')
    
    def setPath(self, cmd):
        """ Extract all the pathname parts from the command and configure (or create) the ExpPath. """

        req, notMatched, leftovers = cmd.match([('name', cmd.qstr),
                                                ('seq', str),
                                                ('places', int)])
        path = self.getPath(cmd)
        
        if req.has_key('name'):
            path.setName(req['name'])
        if req.has_key('seq'):
            path.setNumber(req['seq'])
        if req.has_key('places'):
            path.setPlaces(req['places'])
            
        return path

    def getPath(self, cmd):
        """ Return an existing or new ExpPath for the given program+instrument. """
        
        id = cmd.program()
        try:
            path = self.paths[id]
        except KeyError, e:
            path = ExpPath.ExpPath(cmd.cmdrName, self.instName)
            self.paths[id] = path

        return path
    
    def seqFinished(self, seq):
        inst = seq.inst
        cmd = seq.cmd

        try:
            self.lastSequence = self.sequence
            del self.sequence
            self.sequence = None
        except Exception, e:
            CPL.log("seqFinished", "exposure sequence for %s was not found." % (self.instName))
            return
        
        cmd.finish('')

    def seqFailed(self, seq, reason):
        inst = seq.inst
        cmd = seq.cmd

        try:
            self.lastSequence = self.sequence
            del self.sequence
            self.sequence = None
        except Exception, e:
            CPL.log("seqFailed", "exposure sequence for %s was not found." % (self.instName))
            return
        
        cmd.fail(reason)

    def normalizeInstname(self, name):
        """ Return the canonical name for a given instrument. """

        return name

    def getIDKey(self, cmd):
        """ Return the key describing a given command and instrument. """

        return "exposeID=%s,%s" % (CPL.qstr(cmd.program()), CPL.qstr(self.instName))

    def getPathID(self, cmd):
        return (cmd.program(), self.instName)

    def returnKeys(self, cmd):
        """ Generate all the keys describing our next file. """
        
        pathKey = self.getPath(cmd).getKey()
        cmd.respond(pathKey)
        
        
    
