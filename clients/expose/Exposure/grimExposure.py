import os
import socket

import CPL
import Parsing
import Exposure

class grimCB(Exposure.CB):
    """ Encapsulate a callback from the various GRIM commands.
    """
    
    def __init__(self, cmd, sequence, exp, what, failOnFail=True, debug=0):
        """
        Args:
           cmd      - a Command to finish or fail. Can be None.
           sequence - an ExpSequence to alert on the command success/failure. Can be None.
           what     - a string describing the command.
        """

        Exposure.CB.__init__(self, cmd, sequence, what, failOnFail=failOnFail, debug=debug+3)
        self.exposure = exp

    def cbDribble(self, res):
        """ Handle per-line command replies.
        """

        if self.debug > 0:
            CPL.log("grimCB.cbDribble", "res=%s" % (res))
        try:
            # Check for new exposureState:
            maybeNewState = res.KVs.get('GRIMTXT', None)
            newState = None
            
            # Guess at their length (this is for GRIM only)
            if maybeNewState != None:
                maybeNewState = eval(maybeNewState, {}, {})
                
                length = 0.0
                if maybeNewState == 'flushing...':
                    newState = "flushing"
                elif maybeNewState == 'integrating...':
                    length = self.exposure.expTime
                    newState = "integrating"
                    self.exposure.integrationStarted()
                elif maybeNewState == 'Sending image to MC':
                    newState = "processing"
                elif maybeNewState == 'integration aborted':
                    CPL.log("grim.dribble", "aborted what=%s newState=%s" % (self.what, maybeNewState))
                    if self.exposure.aborting:
                        newState = "aborted"
                    else:
                        self.exposure.finishUp()
                        newState = "done"
                elif maybeNewState == 'Done':
                    self.exposure.finishUp()
                    newState = "done"

            if newState != None:
                CPL.log('grimCB.cbDribble', "newstate=%s seq=%s" % (newState, self.sequence))
                if self.exposure:
                    self.exposure.setState(newState, length)
        except Exception, e:
            CPL.log('dribble', 'exposureState barf = %s' % (e))
        
        Exposure.CB.cbDribble(self, res)
        

class grimExposure(Exposure.Exposure):
    def __init__(self, actor, seq, cmd, path, expType, **argv):
        Exposure.Exposure.__init__(self, actor, seq, cmd, path, expType, **argv)

        # Look for Grim-specific options & arguments.
        #
        req, notMatched, leftovers = cmd.match([('time', float),
                                                ('comment', Parsing.dequote)])
        self.instArgs = req

        self.comment = req.get('comment', None)

        if expType in ("object", "dark", "flat"):
            if req.has_key('time'):
                t = req['time']
                if t <= 1.21:
                    raise Exception("exposure time must be >= 1.21s")
                self.expTime = t
            else:
                raise Exception("%s exposures require a time argument" % (expType))

        self.reserveFilenames()
        self.aborting = False
        
    def reserveFilenames(self):
        """ Reserve filenames, and set .basename.
        """

        # self.cmd.warn('debug=%s' % (CPL.qstr("reserve: %s" % self.path)))
        self.pathParts = self.path.getFilenameInParts(keepPath=True)

    def _basename(self):
        return os.path.join(*self.pathParts)

    def integrationStarted(self):
        """ Called when the integration is _known_ to have started. """

        outfile = self._basename()
        if self.debug > 1:
            CPL.log("grimExposure", "starting grim FITS header to %s" % (outfile))

        cmdStr = 'start grim outfile=%s' % (outfile)
        if self.comment:
            cmdStr += ' comment=%s' % (CPL.qstr(self.comment))
        self.callback('fits', cmdStr)
        
    def finishUp(self):
        """ Clean up and close out the FITS files.

        This is HORRIBLE! -- we are blocking at the worst time for the exposure. FIX THIS!!!
        
        """

        CPL.log("grim.finishUp", "state=%s" % (self.state))

        if self.state != "aborted":
            self.callback('fits', 'finish grim inkey=scratchFile')
        else:
            self.callback('fits', 'abort grim')
            
    def lastFilesKey(self):
        return self.filesKey(keyName="grimFiles")
    
    def newFilesKey(self):
        return self.filesKey(keyName="grimNewFiles")
    
    def filesKey(self, keyName="grimFiles"):
        """ Return a fleshed out key variable describing our files.

        We return all the parts separately, in a form that can be
        handed to os.path.join(), at least on another Unix box.
        
        """
        
        filebase = self.pathParts[-1]
        userDir = self.pathParts[-2]
        if userDir != '':
            userDir += os.sep
            
        return "%s=%s,%s,%s,%s,%s,%s" % \
               (keyName,
                CPL.qstr(self.cmd.cmdrName),
                CPL.qstr('newton.apo.nmsu.edu'),
                CPL.qstr(self.pathParts[0] + os.sep),
                CPL.qstr(self.pathParts[1] + os.sep),
                CPL.qstr(userDir),
                CPL.qstr(self.pathParts[-1]))

    def bias(self):
        """ Start a single bias. Requires several self. variables. """

        self.sequence.exposureFailed('exposeTxt="grim does not take biases."')
        
    def _expose(self, type):
        """ Start a single object exposure. Requires several self. variables. """

        cb = grimCB(None, self.sequence, self, type)
        r = self.callback("grim", "integrate: %d" % (int(self.expTime * 1000)),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
    def object(self):
        """ Start a single flat. Requires several self. variables. """

        self._expose('object')
        
    def flat(self):
        """ Start a single flat. Requires several self. variables. """

        self._expose('flat')
        
    def dark(self):
        """ Start a single dark. Requires several self. variables. """

        self._expose('dark')
        
    def stop(self, cmd, **argv):
        """ Stop the current exposure: cause it to read out immediately, and save the data. """

        cb = grimCB(cmd, None, self, "stop", failOnFail=False)
        self.callback("grim", "abort:",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
                
    def abort(self, cmd, **argv):
        """ Stop the current exposure immediately, and DISCARD the data. """

        self.aborting = True
        
        cb = grimCB(cmd, None, self, "abort", failOnFail=False)
        self.callback("grim", "abort:",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def pause(self, cmd, **argv):
        """ Pause the current exposure. """

        cmd.fail('exposeTxt="grim exposures cannot be paused."')
        
    def resume(self, cmd, **argv):
        """ Resume the current exposure. """

        cmd.fail('exposeTxt="grim exposures cannot be paused or resumed."')

        
        
