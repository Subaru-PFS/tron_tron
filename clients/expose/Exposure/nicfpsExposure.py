import os
import socket
import time

import CPL
import Parsing
import Exposure

class nicfpsCB(Exposure.CB):
    """ Encapsulate a callback from the various NICFPS exposure commands.
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
            CPL.log("nicfpsCB.cbDribble", "res=%s" % (res))
        try:
            # Check for new exposureState:
            maybeNewState = res.KVs.get('exposureStatus', None)
            CPL.log("nicfpsCB.cbDribble", "exposureStatus=%s" % (maybeNewState))
            newState = None

            # Extract the expected duration from the exposureState keyword
            if maybeNewState != None:
                maybeNewState, length = maybeNewState
                length = float(length)
                CPL.log("nicfpsCB.cbDribble", "newState=%s, length=%0.2f" % (maybeNewState, length))
                
                if maybeNewState in ('clearing', 'reading'):
                    newState = maybeNewState
                elif maybeNewState == 'integrating':
                    newState = maybeNewState
                    self.exposure.integrationStarted()
                elif maybeNewState == 'aborted':
                    CPL.log("nicfps.dribble", "aborted what=%s newState=%s" % (self.what, maybeNewState))
                    if self.exposure.aborting:
                        newState = "aborted"
                    else:
                        newState = "done"
                        self.exposure.finishUp()
                elif maybeNewState == 'done':
                    newState = maybeNewState
                    self.exposure.finishUp()
                    
            if newState != None:
                CPL.log('nicfpsCB.cbDribble', "newstate=%s seq=%s" % (newState, self.sequence))
                if self.exposure:
                    self.exposure.setState(newState, length)
        except Exception, e:
            CPL.log('dribble', 'exposureState barf = %s' % (e))
        
        Exposure.CB.cbDribble(self, res)
        

class nicfpsExposure(Exposure.Exposure):
    def __init__(self, actor, seq, cmd, path, expType, **argv):
        Exposure.Exposure.__init__(self, actor, seq, cmd, path, expType, **argv)

        # Look for Nicfps-specific options & arguments.
        #
        req, notMatched, leftovers = cmd.match([('time', float),
                                                ('comment', Parsing.dequote)])
        self.instArgs = req

        self.comment = req.get('comment', None)

        if expType in ("object", "dark", "flat"):
            if req.has_key('time'):
                self.expTime = req['time']
            else:
                raise Exception("%s exposures require a time argument" % (expType))

        # Where NICFPS puts its image files.
        self.rawDir = '/export/images/nicfps/forTron'

        self.reserveFilenames()
        self.aborting = False

    def reserveFilenames(self):
        """ Reserve filenames, and set .basename.
        """

        # self.cmd.warn('debug=%s' % (CPL.qstr("reserve: %s" % self.path)))
        self.pathParts = self.path.getFilenameInParts(keepPath=True)

        # HACK - squirrel away a directory listing to compare with later.
        self.startDirList = os.listdir(self.rawDir)
        
    def _basename(self):
        return os.path.join(*self.pathParts)

    def integrationStarted(self):
        """ Called when the integration is _known_ to have started. """

        outfile = self._basename()
        if self.debug > 1:
            CPL.log("nicfpsExposure", "starting nicfps FITS header to %s" % (outfile))

        cmdStr = 'start nicfps outfile=%s' % (outfile)
        if self.comment:
            cmdStr += ' comment=%s' % (CPL.qstr(self.comment))
        self.callback('fits', cmdStr)

    def getNewRawFile(self):
        """ Wait for a new raw file to appear and be completed. """

        self.cmd.warn('debug="waiting for new NICFPS file in %s; %d files"' % \
                      (self.rawDir, len(self.startDirList)))

        # How long to wait for a new image file
        loopTime = 30.0

        # How often to check for a new file:
        waitTime = 0.5
        
        while 1:
            newList = os.listdir(self.rawDir)
            self.cmd.warn('debug="NICFPS exposure: %d files"' % (len(newList)))
            if len(newList) != len(self.startDirList):
                break

            loopTime -= waitTime
            if loopTime <= 0.0:
                self.state = 'aborted'
                self.cmd.fail('errorTxt="NICFPS exposure timed out."')
                return
            time.sleep(waitTime)

        # Now find the new file and wait for the readout to complete.
        newList.sort()
        newFile = os.path.join(self.rawDir, newList[-1])
        self.cmd.warn('debug="NICFPS exposure: %s"' % (newFile))

        finalSize = 2102400L
        while 1:
            stat = os.stat(newFile)
            if stat[6] == finalSize:
                return newFile
            time.sleep(0.1)
        self.cmd.warn('debug="full NICFPS exposure: %s"' % (newFile))
            
    def finishUp(self):
        """ Clean up and close out the FITS files.

        This is HORRIBLE! -- we are blocking at the worst time for the exposure. FIX THIS!!!
        
        """

        CPL.log("nicfps.finishUp", "state=%s" % (self.state))

        rawFile = self.getNewRawFile()
        
        if self.state != "aborted":
            self.callback('fits', 'finish nicfps infile=%s' % (rawFile))
        else:
            self.callback('fits', 'abort nicfps')
            
    def lastFilesKey(self):
        return self.filesKey(keyName="nicfpsFiles")
    
    def newFilesKey(self):
        return self.filesKey(keyName="nicfpsNewFiles")
    
    def filesKey(self, keyName="nicfpsFiles"):
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
                CPL.qstr('tycho.apo.nmsu.edu'),
                CPL.qstr(self.pathParts[0] + os.sep),
                CPL.qstr(self.pathParts[1] + os.sep),
                CPL.qstr(userDir),
                CPL.qstr(self.pathParts[-1]))

    def bias(self):
        """ Start a single bias. Requires several self. variables. """

        self.sequence.exposureFailed('exposeTxt="nicfps does not take biases."')
        
    def _expose(self, type):
        """ Start a single object exposure. Requires several self. variables. """

        cb = nicfpsCB(None, self.sequence, self, type)
        r = self.callback("nicfps", "expose object time=%0.2f" % (self.expTime),
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

        cb = nicfpsCB(cmd, None, self, "stop", failOnFail=False)
        self.callback("nicfps", "expose stop",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
                
    def abort(self, cmd, **argv):
        """ Stop the current exposure immediately, and DISCARD the data. """

        self.aborting = True
        
        cb = nicfpsCB(cmd, None, self, "abort", failOnFail=False)
        self.callback("nicfps", "expose abort",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def pause(self, cmd, **argv):
        """ Pause the current exposure. """

        cmd.fail('exposeTxt="nicfps exposures cannot be paused."')
        
    def resume(self, cmd, **argv):
        """ Resume the current exposure. """

        cmd.fail('exposeTxt="nicfps exposures cannot be paused or resumed."')

        
        
