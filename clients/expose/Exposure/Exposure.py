import math
import os
import socket
import time

import CPL
import Actor

class Exposure(Actor.Acting):            
    """ Handle a single exposure. """

    states = ('idle',
              'flushing',
              'integrating',
              'paused',
              'reading',
              'done',
              'aborted')
              
    def __init__(self, actor, sequence, cmd, path, expType, **argv):
        Actor.Acting.__init__(self, actor, **argv)
        
        self.debug = argv.get('debug', 0)

        self.sequence = sequence
        self.cmd = cmd
        self.path = path
        self.expType = expType

        self.stateMark = 0.0
        self.stateLength = 0.0
        self.expTime = 0.0
        self.expLeft = self.expTime
        self.alreadyStarted = False
        
        self.setState('idle')
        
    def run(self):
        """ Call the real exposure method. """

        self.__class__.__dict__[self.expType](self)
        
    def setState(self, newState, expectedLength=0.0, mark=None):
        """ Set the exposure state and update the timers.

        We track the time of the start of the state and the expected time left.
        """

        CPL.log("Exposure", "setState %s %s %s" % (newState, expectedLength, mark))
        
        if mark == None:
            mark = time.time()

        # For paused and integrating states, reset expLeft.
        if newState == 'integrating':
            if self.state != 'paused':
                self.expLeft = self.expTime
            self.stateMark = mark
            expectedLength = self.expLeft
        elif newState == 'paused':
            self.expLeft -= (mark - self.stateMark)
            self.stateMark = mark
            expectedLength = self.expLeft
        else:
            self.stateMark = mark

        self.state = newState
        self.stateLength = expectedLength

        if self.state != 'idle':
            newKey = self.getStateKeys()
            self.cmd.respond(newKey)
        
    def getStateKeys(self):
        """ Return a keyword describing our state.

        instExpState=username,state,stateStart,expectedStateLeft,totalForState

        The TUI uses this to fill in the expose displays.
        """

        now = time.time()
        if self.state in ('idle', 'done', 'aborted'):
            times = [0.0, 0.0]
        elif self.state == 'paused':
            times = [self.stateLength, self.expTime]
        elif self.state == 'integrating':
            expectedStateLeft = (self.stateMark + self.stateLength) - now
            times = [expectedStateLeft, self.expTime]
        else:
            expectedStateLeft = (self.stateMark + self.stateLength) - now
            times = [expectedStateLeft, self.stateLength]
            
        markString = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(self.stateMark)) \
                     + ".%1dZ" % (10 * math.modf(self.stateMark)[0])
        
        if times[0] < 0.0:
            times[0] = 0.0
        if times[1] < 0.0:
            times[1] = 0.0
            
        return "%sExpState=%s,%s,%s,%0.1f,%0.1f" % \
               (self.sequence.inst,
                CPL.qstr(self.cmd.fullname),
                CPL.qstr(self.state),
                markString, times[0], times[1])
    
    def getFilenames(self):
        return []
    
    def start(self):
        pass

    def finishUp(self):
        pass

    def fail(self):
        pass
    
class CB(object):
    """ Encapsulate a callback that can handle both the sequence and some control command.  """
    
    def __init__(self, cmd, sequence, what, failOnFail=True, debug=0):
        """
        Args:
           cmd      - a Command to finish or fail. Can be None.
           sequence - an ExpSequence to alert on the command success/failure. Can be None.
           what     - a string describing the command.
        """

        self.debug = debug
        self.failOnFail = failOnFail
        
        self.cmd = cmd
        self.sequence = sequence
        self.what = what

    def cb(self, res):
        """ Handle a complete command reply. We only care about the 'ok' field, which
            tells whether the command succeeded or failed.
        """

        if self.debug > 0:
            CPL.log("CB.cb", "res=%s" % (res))
        
        if res.ok:
            if self.sequence:
                self.sequence.nextInSequence()
            if self.cmd:
                self.cmd.finish('exposeTxt="%s done"' % (self.what))
        else:
            if self.sequence:
                if self.failOnFail:
                    self.sequence.exposureFailed('exposeTxt="%s failed"' % (self.what))
                else:
                    self.sequence.nextInSequence()
            if self.cmd:
                if self.failOnFail:
                    self.cmd.fail('exposeTxt="%s failed"' % (self.what))
                else:
                    self.cmd.warn('exposeTxt="possible problem with %s"' % (self.what))
                    self.cmd.finish('')
                    
                    
    def cbDribble(self, res):
        """ Handle per-line command replies.
        """

        if self.debug > 0:
            CPL.log("CB.cb", "res=%s" % (res))
        
        done = res.flag in 'fF:'
        failed = res.flag in 'fF'

        if done:
            if failed:
                if self.sequence:
                    if self.failOnFail:
                        self.sequence.exposureFailed('exposeTxt="%s failed"' % (self.what))
                    else:
                        self.sequence.nextInSequence()
                if self.cmd:
                    if self.failOnFail:
                        self.cmd.fail('exposeTxt="%s failed"' % (self.what))
                    else:
                        self.cmd.warn('exposeTxt="problem with %s"' % (self.what))
                        self.cmd.finish('')
                    
            else:
                if self.sequence:
                    self.sequence.nextInSequence()
                if self.cmd:
                    self.cmd.finish('exposeTxt="%s done"' % (self.what))
                    
        
