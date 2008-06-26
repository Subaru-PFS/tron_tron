import os
import socket
import time

import CPL
import Parsing
import Exposure

class disCB(Exposure.CB):
    """ Encapsulate a callback from the various DIS commands.
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
            CPL.log("disCB.cbDribble", "res=%s" % (res))
        try:
            # Check for new exposureState:
            newStateRaw = res.KVs.get('exposureState', None)
            if not newStateRaw:
                Exposure.CB.cbDribble(self, res)
                return
            try:
                #self.exposure.cmd.warn('debug=%s' % (CPL.qstr("newstateRaw:%s:" % (newStateRaw))))
                newState,t = newStateRaw
                length = float(t)
            except:
                self.exposure.cmd.warn('text=%s' % (CPL.qstr('exposureState barf = %s' % (e))))
                CPL.log('dribble', 'exposureState barf1 = %s' % (e))

            #self.exposure.cmd.warn('debug=%s' % (CPL.qstr("newstate:%s,%0.2f" % (newState,length))))
            if newState == 'integrating' or (newState == 'reading' and self.what == 'bias'):
                self.exposure.integrationStarted()
            elif newState == 'aborted':
                self.exposure.finishUp(aborting=True)
            elif newState == 'done':
                self.exposure.finishUp()
                    
            CPL.log('disCB.cbDribble', "newstate=%s seq=%s what=%s" % (newState, self.sequence,self.what))
            self.exposure.setState(newState, length)
        except Exception, e:
            self.exposure.cmd.warn('text=%s' % (CPL.qstr('exposureState barf = %s' % (e))))
        
        Exposure.CB.cbDribble(self, res)
        

class disExposure(Exposure.Exposure):
    def __init__(self, actor, seq, cmd, path, expType, **argv):
        Exposure.Exposure.__init__(self, actor, seq, cmd, path, expType, **argv)

        # Look for DIS-specific options & arguments.
        #
        opts, notMatched, leftovers = cmd.match([('red', None), ('blue', None),
                                                 ('time', float),
                                                 ('comment', Parsing.dequote)])

        # Fetch the camera list. Default to empty, which means both cameras.
        #
        self.cameras = ""
        if opts.has_key('red'):
            if not opts.has_key('blue'):
                self.cameras = "red "
        else:
            if opts.has_key('blue'):
                self.cameras = "blue "
            
        self.comment = opts.get('comment', None)
        self.commentArg = ""
        if self.comment != None:
            self.commentArg = 'comment=%s ' % (CPL.qstr(self.comment))

        if expType in ("object", "dark", "flat"):
            try:
                self.expTime = opts['time']
            except:
                raise Exception("%s exposures require a time argument" % (expType))

        self.rawDir = ('/export/images/forTron/dis')
        self.reserveFilenames()

    def genScratchNames(self):
        """ Generate a filename for the ICC to write to.

        Returns:
           filename  - a filename which is known not to exist now.
        """

        n = 1
        timestamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        while 1:
            basename = "%s%02d" % (timestamp, n)
            filenameb = basename + "b.fits"
            filenamer = basename + "r.fits"
            pathnameb = os.path.join(self.rawDir, filenameb)
            pathnamer = os.path.join(self.rawDir, filenamer)
            if os.path.exists(filenameb) or os.path.exists(filenamer):
                n += 1
                self.cmd.warn('debug="raw filename %s existed"' % pathname)
            else:
                break

            if n > 98:
                raise RuntimeException("Could not create a scratch file for dis. Last tried %s" % (pathname))

        self.scratchNames = {}
        self.scratchNames['base'] = os.path.join(self.rawDir, basename)
        self.scratchNames['red'] = self.scratchNames['base'] + "r.fits"
        self.scratchNames['blue'] = self.scratchNames['base'] + "b.fits"

    def reserveFilenames(self):
        """ Reserve filenames, and set .basename.

        The trick here is that DIS appends "r.fits" and "b.fits", so we need to strip off the suffix
        
        """

        self.genScratchNames()
        parts = list(self.path.getFilenameInParts(keepPath=True))
        basename = os.path.splitext(parts[-1])[0]
        parts[-1] = basename
        
        self.pathParts = parts
        self.outfiles = {}
        if self.cameras in ('', 'red '):
            self.outfiles['red'] = self._basename() + "r.fits"
        if self.cameras in ('', 'blue '):
            self.outfiles['blue'] = self._basename() + "b.fits"
            
    def _basename(self):
        return os.path.join(*self.pathParts)

    def lastFilesKey(self):
        return self.filesKey(keyName="disFiles")
    
    def newFilesKey(self):
        return self.filesKey(keyName="disNewFiles")
    
    def filesKey(self, keyName="disFiles"):
        """ Return a fleshed out key variable describing our files.

        We return all the parts separately, in a form that can be
        handed to os.path.join(), at least on another Unix box.
        
        """
        
        filebase = self.pathParts[-1]
        userDir = self.pathParts[-2]
        if userDir != '':
            userDir += os.sep
            
        if self.cameras == "":
            blueFile = CPL.qstr("%sb.fits" % (filebase))
            redFile = CPL.qstr("%sr.fits" % (filebase))
        elif self.cameras == "red ":
            blueFile = 'None'
            redFile = CPL.qstr("%sr.fits" % (filebase))
        else:
            blueFile = CPL.qstr("%sb.fits" % (filebase))
            redFile = 'None'

        return "%s=%s,%s,%s,%s,%s,%s,%s" % \
               (keyName,
                CPL.qstr(self.cmd.cmdrName),
                CPL.qstr('newton.apo.nmsu.edu'),
                CPL.qstr(self.pathParts[0] + os.sep),
                CPL.qstr(self.pathParts[1] + os.sep),
                CPL.qstr(userDir),
                blueFile, redFile)
        
    def integrationStarted(self):
        """ Called when the integration is _known_ to have started. """

        # self.cmd.warn("debug='starting DIS FITS header with %s'" % (self.cameras))

        if self.alreadyStarted:
            return
        self.alreadyStarted = True
        

        if self.cameras in ('', 'red '):
            cmdStr = 'start disred outfile=%s' % (self.outfiles['red'])
            if self.comment:
                cmdStr += ' comment=%s' % (CPL.qstr(self.comment))
            self.callback('fits', cmdStr)
        if self.cameras in ('', 'blue '):
            cmdStr = 'start disblue outfile=%s' % (self.outfiles['blue'])
            if self.comment:
                cmdStr += ' comment=%s' % (CPL.qstr(self.comment))
            self.callback('fits', cmdStr)

    def finishUp(self, aborting=False):
        """ Clean up and close out the FITS files.

        This is HORRIBLE! -- we are blocking at the worst time for the exposure. FIX THIS!!!
        
        """

        CPL.log("dis.finishUp", "state=%s" % (self.state))

        CPL.log('disExposure', "finishing from rawfile=%s" % (self.scratchNames['base']))
        
        if self.cameras in ('', 'red '):
            if aborting:
                self.callback('fits', 'abort disred')
            else:
                self.callback('fits', 'finish disred infile=%s' % (self.scratchNames['red']))
        if self.cameras in ('', 'blue '):
            if aborting:
                self.callback('fits', 'abort disblue')
            else:
                self.callback('fits', 'finish disblue infile=%s' % (self.scratchNames['blue']))

        
    def _expose(self, type, exptime=None, extra=''):
        """ Start a single exposure. Requires several self. variables. """
         
        cb = disCB(None, self.sequence, self, type, debug=2)
        if exptime != None:
            exptimeArg = "time=%s" % (exptime)
        else:
            exptimeArg = ''
            
        # self.cmd.warn('debug=%s' % (CPL.qstr('firing off exposure callback to %s' % (self.rawpath))))
        r = self.callback("dis", "expose %s %s basename=%s %s %s" % \
                          (type, exptimeArg, self.scratchNames['base'], self.cameras, self.commentArg),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)

    def bias(self):
        """ Start a single bias. Requires several self. variables. """

        self._expose('bias')
        
    def object(self):
        """ Start a single object exposure. Requires several self. variables. """

        self._expose('object', self.expTime)
        
    def flat(self):
        """ Start a single flat exposure. Requires several self. variables. """

        self._expose('flat', self.expTime)
        
    def dark(self):
        """ Start a single dark. Requires several self. variables. """

        self._expose('dark', self.expTime)
        
    def stop(self, cmd, **argv):
        """ Stop the current exposure: cause it to read out immediately, and save the data. """

        cb = disCB(cmd, None, self, "stop", failOnFail=False, debug=2)
        self.callback("dis", "expose stop",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def abort(self, cmd, **argv):
        """ Stop the current exposure immediately, and DISCARD the data. """

        cb = disCB(cmd, None, self, "abort", failOnFail=False, debug=2)
        self.callback("dis", "expose abort",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def pause(self, cmd, **argv):
        """ Pause the current exposure. """

        cb = disCB(cmd, None, self, "pause", failOnFail=False, debug=2)
        self.callback("dis", "expose pause",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def resume(self, cmd, **argv):
        """ Resume the current exposure. """

        if self.state != "paused":
            cmd.fail("disTxt", "can only resume paused exposures")
            return

        cb = disCB(cmd, None, self, "resume", failOnFail=False, debug=2)
        self.callback("dis", "expose resume",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)

        
        
