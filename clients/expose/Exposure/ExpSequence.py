import CPL
import CPL.Exceptions.Error as Error

import Actor
import disExposure
import echelleExposure
import grimExposure

class ExpSequence(Actor.Acting):
    def __init__(self, actor, cmd, inst, expType, path, cnt, **argv):
        Actor.Acting.__init__(self, actor, **argv)
        
        self.actor = actor
        self.cmd = cmd
        self.inst = inst
        self.expType = expType
        self.path = path
        self.cnt = cnt
        self.cntLeft = cnt
        self.argv = argv
        self.state = "running"

        self.exposure = None

    def run(self):
        self.startSequence()

    def _getIDKeyParts(self):
        """ Return the program name, the instrument name, and the username. """

        return qstr(self.cmd.program()), qstr(self.inst), qstr(self.cmd.username())

    def getStateKey(self):
        """
        """

        if self.exposure:
            expTime = self.exposure.expTime
        else:
            expTime = 0.0
            
        seqState = "%sSeqState=%s,%s,%0.1f,%d,%d,%s" % \
                   (self.inst,
                    CPL.qstr(self.cmd.fullname),
                    CPL.qstr(self.expType),
                    expTime,
                    self.cnt - self.cntLeft,
                    self.cnt,
                    CPL.qstr(self.state))

        return seqState
    
    def returnStateKey(self):
        self.cmd.respond(self.getStateKey())
        
    def returnPathKey(self):
        self.cmd.respond(self.path.getKey())
        
    def returnKeys(self):
        """ Generate all the keys describing our last and next files. """

        self.returnStateKey()
        self.returnPathKey()

    def getKeys(self):
        return self.getStateKey(), self.exposure.getStateKeys()

    def _finishExposure(self):
        # If we actually generated image files, let them know.
        if self.exposure and self.exposure.state not in ('idle', 'aborted'):
            CPL.log("seq.finishExposure", "state=%s" % (self.exposure.state))
                    
            # self.exposure.finishUp()
            filesKey = self.exposure.filesKey()
            if filesKey:
                self.cmd.respond(filesKey)

        # If we have reached the end of the sequence, close ourselves out.
        if self.cntLeft <= 0 or self.state in ('stopped', 'aborted'):
            #if self.cntLeft <= 0:
            #    self.state = 'done'
            self.returnKeys()
            self.actor.seqFinished(self)
            return

        # Do not let pausing paper over 
        if self.state == 'paused':
            if self.exposure and self.exposure.state in ('done', 'aborted', 'failed'):
                self.exposure = None
            return
 
        self.exposure = None

    def _startExposure(self):
        # Try-except -- CPL        
        try:
            exec('instrumentExposure = %sExposure.%sExposure' % (self.inst, self.inst))
            self.exposure = instrumentExposure(self.actor, self,
                                               self.cmd, self.path, self.expType, **self.argv)
        except Exception, e:
            self.actor.seqFailed(self, "exposeTxt=%s" % (CPL.qstr(e)))
            return
        
        self.cntLeft -= 1
        self.returnKeys()
        self.exposure.run()
    
    def startSequence(self):
        self._startExposure()
    
    def nextInSequence(self):
        """ Start the next exposure in the sequence.

        This is called after an exposure has finished.
        """

        self._finishExposure()
        if self.cntLeft > 0 and self.state not in ('paused', 'stopped', 'aborted', 'done'):
            self._startExposure()
        
    def exposureFailed(self, reason=""):
        """ Something went wrong with our exposure. Kill ourselves. """

        if self.exposure and self.exposure.state == "aborted":
            self.state = "aborted"
            self.returnKeys()
            self.nextInSequence()
            #self.actor.seqFailed(self, reason)
        else:
            self.state = "failed"
            self.returnKeys()
            self.actor.seqFailed(self, reason)
        
    def stop(self, cmd, **argv):
        self.state = "stopped"
        if self.exposure:
            self.exposure.stop(cmd, **argv)
        else:
            self.nextInSequence()
            
    def abort(self, cmd, **argv):
        self.state = "aborted"
        if self.exposure:
            self.exposure.abort(cmd, **argv)
        else:
            self.nextInSequence()
            
    def pause(self, cmd, **argv):
        self.state = "paused"
        if self.exposure:
            self.exposure.pause(cmd, **argv)
        self.returnStateKey()

    def resume(self, cmd, **argv):
        self.state = "running"
        if self.exposure != None:
            self.exposure.resume(cmd, **argv)
            self.returnStateKey()
        else:
            self.nextInSequence()


