import os
import socket

import CPL

import Exposure

class echelleCB(Exposure.CB):
    """ Encapsulate a callback from the various ECHELLE commands.
    """
    
    def __init__(self, cmd, sequence, exp, what, failOnFail=True, debug=0):
        """
        Args:
           cmd      - a Command to finish or fail. Can be None.
           sequence - an ExpSequence to alert on the command success/failure. Can be None.
           exp      - an Exposure to alert to state changes.
           what     - a string describing the command.
        """

        Exposure.CB.__init__(self, cmd, sequence, what, failOnFail=failOnFail, debug=debug)
        self.exposure = exp
        
    def cbDribble(self, res):
        """ Handle per-line command replies.
        """

        if self.debug > 0:
            CPL.log("echelleCB.cbDribble", "res=%s" % (res))
        try:
            # Check for new exposureState:
            maybeNewState = res.KVs.get('ECHELLETXT', None)
            newState = None
            
            # Guess at their length (this is for ECHELLE only)
            if maybeNewState != None:
                maybeNewState = eval(maybeNewState, {}, {})
                CPL.log("echelle.cbDribble", "maybeNewState=%s" % (maybeNewState))
                        
                length = 0.0
                if maybeNewState == 'flushing...':
                    newState = "flushing"
                    length = 37.0
                elif maybeNewState in ('integrating...', 'resuming'):
                    newState = "integrating"
                    self.exposure.integrationStarted()
                elif maybeNewState == 'pausing':
                    newState = "paused"
                elif maybeNewState == 'integration aborted, will not read chip':
                    newState = "aborted"
                elif maybeNewState in ('reading chip...', 'stopping'):
                    newState = "reading"
                    length = 115.0
                elif maybeNewState == 'Sending image to MC':
                    newState = "processing"
                    length = 12.0
                elif maybeNewState in ('Done', 'integration stopped prematurely, chip was read'):
                    self.exposure.finishUp()
                    newState = "done"
                    
            if newState != None:
                CPL.log('echelleCB.cbDribble', "newstate=%s seq=%s" % (newState, self.sequence))
                if self.exposure:
                    self.exposure.setState(newState, length)
        except Exception, e:
            CPL.log('dribble', 'exposureState barf = %s' % (e))
        
        Exposure.CB.cbDribble(self, res)
        
class echelleExposure(Exposure.Exposure):
    def __init__(self, actor, seq, cmd, path, expType, **argv):
        Exposure.Exposure.__init__(self, actor, seq, cmd, path, expType, **argv)

        # Look for Echelle-specific options & arguments.
        #
        req, notMatched, leftovers = cmd.match([('time', float),
                                                ('comment', str)])
        self.instArgs = req

        self.comment = ""
        if req.has_key('comment'):
            self.comment='comment=%s ' % req['comment']

        if expType in ("object", "dark", "flat"):
            if req.has_key('time'):
                t = req['time']
                self.expTime = t
            else:
                raise Exception("%s exposures require a time argument" % (expType))
            
        self.reserveFilenames()

    def reserveFilenames(self):
        """ Reserve filenames, and set .basename.
        """

        self.pathParts = self.path.getFilenameInParts(keepPath=True)

    def _basename(self):
        return os.path.join(*self.pathParts)
    
    def integrationStarted(self):
        """ Called when the integration is _known_ to have started. """

        if self.state == "paused":
            return
        
        if self.debug > 1:
            CPL.log("echelleExposure", "starting echelle FITS header")
        self.callback('fits', 'start echelle')
        
    def finishUp(self):
        """ Clean up and close out the FITS files.

        This is HORRIBLE! -- we are blocking at a) the worst time for the exposure, and b) in a way
        that can block _other_ instruments!  FIX THIS!!!
        
        """

        output = self._basename()
        if self.debug > 1:
            CPL.log("echelleExposure", "finishing echelle FITS header for %s" % (output))
        if self.state != "aborted":
            self.callback('fits', 'finish echelle %s' % (output))

    def filesKey(self):
        """ Return a fleshed out key variable describing our files.

        We return all the parts separately, in a form that can be
        handed to os.path.join(), at least on another Unix box.
        
        """
        
        filebase = self.pathParts[-1]
        userDir = self.pathParts[-2]
        if userDir != '':
            userDir += os.sep
            
        return "echelleFiles=%s,%s,%s,%s,%s,%s" % \
               (CPL.qstr(self.cmd.cmdrName),
                CPL.qstr('tycho.apo.nmsu.edu'),
                CPL.qstr(self.pathParts[0] + os.sep),
                CPL.qstr(self.pathParts[1] + os.sep),
                CPL.qstr(userDir),
                CPL.qstr(self.pathParts[-1]))
                
        
    def bias(self):
        """ Start a single bias. Requires several self. variables. """

        cb = echelleCB(None, self.sequence, self, "bias")
        r = self.callback("echelle", "bias: 0",
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
    def _expose(self, type):
        """ Start a single object exposure. Requires several self. variables. """

        cb = echelleCB(None, self.sequence, self, type)
        r = self.callback("echelle", "integrate: %d" % (int(self.expTime * 1000)),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
    def object(self):
        self._expose('object')
        
    def flat(self, **argv):
        self._expose('flat')
        
    def dark(self):
        """ Start a single dark. Requires several self. variables. """

        cb = echelleCB(None, self.sequence, self, "dark")
        r = self.callback("echelle", "dark: %d" % (int(self.expTime * 1000)),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
    def stop(self, cmd, **argv):
        """ Stop the current exposure: cause it to read out immediately, and save the data. """

        cb = echelleCB(cmd, None, self, "stop", failOnFail=False)
        self.callback("echelle", "stop:",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
        
    def abort(self, cmd, **argv):
        """ Stop the current exposure immediately, and DISCARD the data. """

        cb = echelleCB(cmd, None, self, "abort", failOnFail=False)
        self.callback("echelle", "abort:",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def pause(self, cmd, **argv):
        """ Pause the current exposure. """

        cb = echelleCB(cmd, None, self, "pause", failOnFail=False)
        self.callback("echelle", "pause:",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def resume(self, cmd, **argv):
        """ Resume the current exposure. """

        cb = echelleCB(cmd, None, self, "resume", failOnFail=False)
        self.callback("echelle", "resume:",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        

        
        
