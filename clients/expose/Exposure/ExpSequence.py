import CPL
import CPL.Exceptions.Error as Error

import Actor
import disExposure
import echelleExposure
import grimExposure
import nicfpsExposure
import spicamExposure
import tspecExposure

class ExpSequence(Actor.Acting):
    '''
    Hi level object that controls an exposure.  It calls lower level Exposure
    objects to command the camera.
    '''
    def __init__(self, actor, cmd, inst, expType, path, cnt, **argv):
        """ Track 
        """
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

        self.startNum = argv.get('startNum', None)
        self.totNum = argv.get('totNum', cnt)
        
        self.exposure = None
        self.path.newSequence()
        
    def run(self):
        self.startSequence()

    def _getIDKeyParts(self):
        """ Return the program name, the instrument name, and the username. """

        return CPL.qstr(self.cmd.program()), CPL.qstr(self.inst), CPL.qstr(self.cmd.username())

    def getStateKey(self):
        """
        """

        if self.exposure:
            expTime = self.exposure.expTime
        else:
            expTime = 0.0

        # Possibly lie about how we are progressing
        #
        if self.startNum != None:
            cnt = (self.cnt - self.cntLeft) + (self.startNum - 1)
        else:
            cnt = self.cnt - self.cntLeft

        state = self.state
        if state == 'done' and self.totNum != cnt:
            state = 'subsequence done'

        seqState = "%sSeqState=%s,%s,%0.1f,%d,%d,%s" % \
                   (self.inst,
                    CPL.qstr(self.cmd.fullname),
                    CPL.qstr(self.expType),
                    expTime,
                    cnt,
                    self.totNum,
                    CPL.qstr(state))

        return seqState
    
    def returnStateKey(self):
        self.cmd.respond(self.getStateKey())
        
    def returnPathKey(self):
        self.cmd.respond(self.exposure.lastFilesKey())

    def returnNewFilesKey(self):
        self.cmd.respond(self.exposure.newFilesKey())
        
    def returnKeys(self):
        """ Generate all the keys describing our last and next files. """

        self.returnStateKey()
        self.cmd.respond('comment=%s' % (CPL.qstr(self.exposure.comment)))
        # self.returnPathKey()
        self.cmd.respond(self.path.getKey())
        
    def getKeys(self):
        return self.getStateKey(), self.exposure.getStateKeys()
    
    def _finishExposure(self):
        """ Called when one of our exposures is finished.
        """
        
        # If we actually generated image files, let them know.
        if self.exposure and self.exposure.state not in ('idle', 'aborted'):
            CPL.log("seq.finishExposure", "state=%s" % (self.exposure.state))
                    
            # self.exposure.finishUp()
            filesKey = self.exposure.lastFilesKey()
            if filesKey:
                self.cmd.respond(filesKey)

        # If we have reached the end of the sequence, close ourselves out.
        if self.cntLeft <= 0 or self.state in ('stopped', 'aborted'):
            if self.state not in ('stopped', 'aborted'):
                self.state = 'done'
            #CPL.log("seq.exposureFailed", "cnt left %s, state %s" % (str(self.cntLeft),self.state))
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
        self.returnNewFilesKey()
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
            #CPL.log("seq.exposureFailed", "1")
            self.returnKeys()
            self.nextInSequence()
            #self.actor.seqFailed(self, reason)
        else:
            self.state = "failed"
            #CPL.log("seq.exposureFailed", "2")
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


