import os
import socket
import time

import CPL
import Parsing
import Exposure

class echelleCB(Exposure.CB):
    """ Encapsulate a callback from the various ECHELLE commands.
    """
    
    def __init__(self, cmd, sequence, exp, what, failOnFail=True, debug=0):
        """
        Args:
           cmd      - a Command to finish or fail. Can be None.
           sequence - an ExpSequence to alert on the command success/failure. Can be None.
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
            maybeNewState = res.KVs.get('exposureState', None)
            CPL.log("echelleCB.cbDribble", "exposureState=%s" % (maybeNewState))
            newState = None
            
            # Guess at their length
            if maybeNewState != None:
                maybeNewState, length = maybeNewState
                maybeNewState = Parsing.dequote(maybeNewState)
                length = float(length)
                CPL.log('echelleCB.cbDribble', "newstate=%s length=%0.2f" % (maybeNewState, length))

                if maybeNewState in ('flushing', 'reading', 'paused', 'finishing'):
                    newState = maybeNewState
                elif maybeNewState in ('integrating', 'bias'):
                    newState = maybeNewState
                    self.exposure.integrationStarted()
                elif maybeNewState == 'aborted':
                    CPL.log("nicfps.dribble", "aborted what=%s newState=%s" % (self.what, maybeNewState))
                    newState = None
                    self.exposure.finishUp(aborting=True)
                elif maybeNewState == 'done':
                    newState = None
                    self.exposure.finishUp()

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
        opts, notMatched, leftovers = cmd.match([('time', float),
                                                 ('comment', Parsing.dequote)])

        self.comment = opts.get('comment', None)
        self.commentArg = ""
        if self.comment != None:
            self.commentArg = 'comment=%s ' % (CPL.qstr(self.comment))

        if expType in ("object", "dark", "flat"):
            try:
                self.expTime = opts['time']
            except:
                raise Exception("%s exposures require a time argument" % (expType))

        # Where the Echelle puts its image files.
        self.rawDir = ('/export/images/forTron/echelle', '')

        self.reserveFilenames()
        self.aborting = False
        self.headerStarted = False
        
    def reserveFilenames(self):
        """ Reserve filenames, and set .basename.

        """

        self.pathParts = self.path.getFilenameInParts(keepPath=True)

    def _basename(self):
        return os.path.join(*self.pathParts)

    def integrationStarted(self):
        """ Called when the integration is _known_ to have started. """

        if self.headerStarted:
            return
            
        outfile = self._basename()
        if self.debug > 1:
            CPL.log("echelleExposure", "starting echelle FITS header to %s" % (outfile))

        cmdStr = 'start echelle outfile=%s' % (outfile)
        if self.comment:
            cmdStr += ' comment=%s' % (CPL.qstr(self.comment))
        self.callback('fits', cmdStr)

        self.headerStarted = True
        
    def finishUp(self, aborting=False):
        """ Clean up and close out the FITS files.

        This is HORRIBLE! -- we are blocking at the worst time for the exposure. FIX THIS!!!
        
        """

        CPL.log("echelle.finishUp", "state=%s" % (self.state))

        rawFile = os.path.join(*self.rawpath)
        CPL.log('echelleExpose', "finishing from rawfile=%s" % (rawFile))
        
        if aborting:
            self.callback('fits', 'abort echelle')
            self.setState('aborted', 0.0)
        else:
            self.callback('fits', 'finish echelle infile=%s' % (rawFile))
            self.setState('done', 0.0)

            
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

            if n > 2:
                raise RuntimeException("Could not create a scratch file for the Echelle. Last tried %s" % (pathname))
            
        return root, path, filename

    def lastFilesKey(self):
        return self.filesKey(keyName="echelleFiles")
    
    def newFilesKey(self):
        return self.filesKey(keyName="echelleNewFiles")
    
    def filesKey(self, keyName="echelleFiles"):
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
        
    
    def _expose(self, cmd):
        """ Start a single object exposure. Requires several self. variables. """

        self.rawpath = self.genRawfileName(self.cmd)
        cb = echelleCB(None, self.sequence, self, cmd)
        r = self.callback("echelle", "expose %s diskname=%s %s" % \
                          (cmd, os.path.join(*self.rawpath), self.commentArg),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
    def bias(self):
        """ Start a single bias. Requires several self. variables. """

        self._expose('bias')
        self.integrationStarted()
        
    def object(self):
        """ Start a single object exposure. Requires several self. variables. """

        self._expose('object time=%0.2f' % (self.expTime))
        
    def flat(self):
        """ Start a single flat exposure. Requires several self. variables. """

        self._expose('flat time=%0.2f' % (self.expTime))
        
    def arc(self):
        """ Start a single flat exposure. Requires several self. variables. """

        self._expose('arc time=%0.2f' % (self.expTime))
        
    def dark(self):
        """ Start a single dark. Requires several self. variables. """

        self._expose('dark time=%0.2f' % (self.expTime))

    def stop(self, cmd, **argv):
        """ Stop the current exposure: cause it to read out immediately, and save the data. """

        cb = echelleCB(cmd, None, self, "stop", failOnFail=False, debug=2)
        self.callback("echelle", "expose stop",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def abort(self, cmd, **argv):
        """ Stop the current exposure immediately, and ECHELLECARD the data. """

        cb = echelleCB(cmd, None, self, "abort", failOnFail=False, debug=2)
        self.callback("echelle", "expose abort",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def pause(self, cmd, **argv):
        """ Pause the current exposure. """

        cb = echelleCB(cmd, None, self, "pause", failOnFail=False, debug=2)
        self.callback("echelle", "expose pause",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def resume(self, cmd, **argv):
        """ Resume the current exposure. """

        if self.state != "paused":
            cmd.fail("echelleTxt", "can only resume paused exposures")
            return

        cb = echelleCB(cmd, None, self, "resume", failOnFail=False, debug=2)
        self.callback("echelle", "expose resume",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)

        
        
