import CPL
import CPL.Exceptions.Error as Error

import Actor
import agileExposure
import disExposure
import echelleExposure
import grimExposure
import nicfpsExposure
import spicamExposure
import tspecExposure

class ExpSequence(Actor.Acting):
    '''
    High level object that controls an exposure.  It calls lower level Exposure
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
        self.cntDone = 0
        self.argv = argv
        self.state = "running"

        self.startNum = argv.get('startNum', None)
        self.totNum = argv.get('totNum', cnt)
        self.instDoesSequence = argv.get('instDoesSequence', False)
        
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
            cnt = self.cntDone+1 + (self.startNum - 1)
        else:
            cnt = self.cntDone+1

        if cnt > self.totNum:
            cnt = self.totNum
            
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

    def reportExposure(self):
        """ Called when one of our exposures is finished, OR when an
            instrument-controlled sequence generates an exposure. """
        
        filesKey = self.exposure.lastFilesKey()
        if filesKey:
            self.cmd.respond(filesKey)
        
    def _finishExposure(self):
        """ Called when one of our exposures is finished.
        """
        
        if self.exposure: expState = self.exposure.state
        else: expState = None
        #self.cmd.warn('debug=" _finishExposure cnt=%s cntDone=%s state=%s expstate=%s"' % (self.cnt, self.cntDone, self.state, expState))

        # If we actually generated image files, let them know.
        if self.exposure and self.exposure.state not in ('idle', 'aborted', 'done'):
            CPL.log("seq.finishExposure", "state=%s" % (self.exposure.state))
            self.reportExposure()
        # If we have reached the end of the sequence, close ourselves out.
        if self.cntDone > self.cnt or self.state in ('stopped', 'aborted', 'done'):
            if self.state not in ('stopped', 'aborted', 'done'):
                self.state = 'done'
            #CPL.log("seq.exposureFailed", "cnt left %s, state %s" % (str(self.cntLeft),self.state))
            self.cmd.warn('debug=" _finishExposure shutting down cnt=%s cntDone=%s"' % (self.cnt, self.cntDone))
            self.returnKeys()
            self.exposure = None
            self.actor.seqFinished(self)
            return

        self.cntDone += 1
        
        # Do not let pausing paper over 
        if self.state == 'paused':
            if self.exposure and self.exposure.state in ('done', 'aborted', 'failed'):
                self.exposure = None
            return

        if not self.instDoesSequence:
            self.exposure = None

    def _startExposure(self):
        # Try-except -- CPL        

        if self.exposure: expState = self.exposure.state
        else: expState = None
        #self.cmd.warn('debug=" _startExposure cnt=%s cntDone=%s state=%s expstate=%s"' % (self.cnt, self.cntDone, self.state, expState))

        if not self.exposure:
            try:
                exec('instrumentExposure = %sExposure.%sExposure' % (self.inst, self.inst))
                self.exposure = instrumentExposure(self.actor, self,
                                                   self.cmd, self.path, self.expType, **self.argv)
            except Exception, e:
                self.actor.seqFailed(self, "exposeTxt=%s" % (CPL.qstr(e)))
                return

        self.returnKeys()
        self.returnNewFilesKey()

        if not self.instDoesSequence or self.cntDone == 0:
            self.exposure.run()
    
    def startSequence(self):
        self._startExposure()
    
    def nextInSequence(self, done=False):
        """ Start the next exposure in the sequence.

        This is called after an exposure has finished.
        """

        if done:
            self.state = 'done'
            
        self._finishExposure()
        if self.state not in ('paused', 'stopped', 'aborted', 'done'):
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


