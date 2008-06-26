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
            maybeNewState = res.KVs.get('exposureState', None)
            CPL.log("nicfpsCB.cbDribble", "exposureState=%s" % (maybeNewState))
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

        if expType in ("object", "dark", "flat", "test"):
            if req.has_key('time'):
                self.expTime = req['time']
            else:
                raise Exception("%s exposures require a time argument" % (expType))

        # Where NICFPS puts its image files.
        self.rawDir = ('/export/images/forTron', 'nicfps')

        self.reserveFilenames()
        self.aborting = False

    def reserveFilenames(self):
        """ Reserve filenames, and set .basename.
        """

        # self.cmd.warn('debug=%s' % (CPL.qstr("reserve: %s" % self.path)))
        self.pathParts = self.path.getFilenameInParts(keepPath=True)

        # HACK - squirrel away a directory listing to compare with later.
        # self.startDirList = os.listdir(self.rawDir)
        
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

    def finishUp(self):
        """ Clean up and close out the FITS files.

        This is HORRIBLE! -- we are blocking at the worst time for the exposure. FIX THIS!!!
        
        """

        CPL.log("nicfps.finishUp", "state=%s" % (self.state))

        rawFile = os.path.join(*self.rawpath)
        CPL.log('nicfpsExposure', "finishing from rawfile=%s" % (rawFile))
        
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
                CPL.qstr('newton.apo.nmsu.edu'),
                CPL.qstr(self.pathParts[0] + os.sep),
                CPL.qstr(self.pathParts[1] + os.sep),
                CPL.qstr(userDir),
                CPL.qstr(self.pathParts[-1]))

    def genRawfileName(self, cmd):
        """ Generate a filename for the ICC to write to.

        Returns:
           root      - the part of the path that only _we_ know and care about,
           path      - the part of the path that both we and the ICC care about.
           filename  - a filename which is known not to exist now.
        """

        root, path = self.rawDir

        n = 1
        timestamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        while 1:
            filename = "%s%02d.fits" % (timestamp, n)
            pathname = os.path.join(root, path, filename)
            if os.path.exists(filename):
                n += 1
                cmd.warn('debug="raw filename %s existed"' % pathname)
            else:
                break

            if n > 98:
                raise RuntimeException("Could not create a scratch file for NICFPS. Last tried %s" % (pathname))
            
        return root, path, filename
    
    def bias(self):
        """ Start a single bias. Requires several self. variables. """

        self.sequence.exposureFailed('exposeTxt="nicfps does not take biases."')

    def _expose(self, type):
        """ Start a single object exposure. Requires several self. variables. """

        self.rawpath = self.genRawfileName(self.cmd)
        cb = nicfpsCB(None, self.sequence, self, type)
        r = self.callback("nicfps", "expose %s time=%0.2f basename=%s" % \
                          (type, self.expTime, os.path.join(*self.rawpath[1:])),
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
        
    def test(self):
        """ Start a single test (ramp) exposure. Requires several self. variables. """

        self._expose('test')
        
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

        
        
