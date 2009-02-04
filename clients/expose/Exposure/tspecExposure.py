import os
import socket
import time

import CPL
import Parsing
import Exposure
import types

class tspecCB(Exposure.CB):
    '''
    Encapsulate a callback from the various TSPEC commands.

    This is the interface to the TSPEC, and it works for the higher level ExpSequence
    instance.
    '''

    
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
            CPL.log("tspecCB.cbDribble", "res=%s" % (res))
        try:
            # Check for new exposureState:
            newStateRaw = res.KVs.get('exposureState', None)
            if not newStateRaw:
                Exposure.CB.cbDribble(self, res)
                return
            mark = None
            try:
                self.exposure.cmd.warn('debug=%s' % (CPL.qstr("newstateRaw:%s:" % (newStateRaw))))
                newState,t,remaining = newStateRaw
                length = float(t)
                remain = float(remaining)
                mark = time.time() - length + remain
                self.exposure.cmd.warn('debug=%s' % (CPL.qstr("newstate:%s,%0.2f,%0.2f" % (newState,length,remain))))
            except Exception, e:
                msg = 'exposureState barf1 = %s' % (str(e))
                CPL.log('dribble', msg);
            newState = newState.replace('"','')
                
            #
            # Exposure states are reading, integrating, processing, done
            #
            if newState == 'reading':
                self.exposure.integrationStarted()
            elif newState == 'aborted':
                self.exposure.finishUp(aborting=True)
            elif newState == 'done':
                self.exposure.finishUp()
                    
            CPL.log('tspecCB.cbDribble', "newstate=%s seq=%s what=%s" % (newState, self.sequence,self.what))
            #self.exposure.cmd.warn('debug=%s' % (CPL.qstr("setting newstate:%s,%0.2f" % (newState,length))))
            self.exposure.setState(newState, length, mark)
        except Exception, e:
            msg = 'exposureState barf = %s' % (str(e))
            CPL.log('dribble', msg)
        
        Exposure.CB.cbDribble(self, res)

class tspecExposure(Exposure.Exposure):
    def __init__(self, actor, seq, cmd, path, expType, **argv):
        Exposure.Exposure.__init__(self, actor, seq, cmd, path, expType, **argv)

        # Look for TSPEC-specific options & arguments.
        #
        opts, notMatched, leftovers = cmd.match([('time', float),
                                                 ('comment', Parsing.dequote),
                                                 ('window',str),
                                                 ('bin',str),
                                                 ('overscan',str)])

        self.comment = opts.get('comment', None)
        self.commentArg = ""
        if self.comment != None:
            self.commentArg = 'comment=%s ' % (CPL.qstr(self.comment))

        if expType in ("object", "dark", "flat"):
            try:
                self.expTime = opts['time']
            except:
                raise Exception("%s exposures require a time argument" % (expType))

        self.geometryString = self.parseGeometry(opts)
        self.rawDir = ('/export/images/forTron/tspec')
        self.reserveFilenames()
        
    def parseGeometry(self, opts):
        """ """

        geometryOpts = []
        if 'window' in opts:
            geometryOpts.append("window=%s" % (opts['window']))
        if 'bin' in opts:
            geometryOpts.append("bin=%s" % (opts['bin']))
        if 'overscan' in opts:
            geometryOpts.append("overscan=%s" % (opts['overscan']))

        return " ".join(geometryOpts)
    
    def reserveFilenames(self):
        """ Reserve filenames, and set .basename.

        """

        self.pathParts = self.path.getFilenameInParts(keepPath=True)

    def _basename(self):
        return os.path.join(*self.pathParts)

    def integrationStarted(self):
        """ Called when the integration is _known_ to have started. """

        CPL.log("tspec.integrationStarted", "already started %s" % (str(self.alreadyStarted)))
        if self.alreadyStarted:
            return
        self.alreadyStarted = True
        
        outfile = self._basename()
        if self.debug > 2:
            self.cmd.warn("debug='starting tspec FITS header to %s'" % (outfile))

        cmdStr = 'start tspec outfile=%s' % (outfile)
        if self.comment:
            cmdStr += ' comment=%s' % (CPL.qstr(self.comment))
        self.callback('fits', cmdStr)

    def finishUp(self, aborting=False):
        """ Clean up and close out the FITS files. """

        #CPL.log("tspec.finishUp", "state=%s" % (self.state))
        #CPL.log('tspecExposure', "finishing from rawfile=%s" % (self.rawpath))
        
        if aborting:
            self.callback('fits', 'abort tspec')
        else:
            self.callback('fits', 'finish tspec infile=%s' % (self.rawpath))

    def genRawfileName(self, cmd):
        """ Generate a filename for the ICC to write to.

        Returns:
           filename  - a filename which is known not to exist now.
        """

        n = 1
        timestamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        while 1:
            filename = "%s%02d.fits" % (timestamp, n)
            pathname = os.path.join(self.rawDir, filename)
            if os.path.exists(filename):
                n += 1
                cmd.warn('debug="raw filename %s existed"' % pathname)
            else:
                break

            if n > 98:
                raise RuntimeException("Could not create a scratch file for tspec. Last tried %s" % (pathname))

        return pathname
    
    def lastFilesKey(self):
        return self.filesKey(keyName="tspecFiles")
    
    def newFilesKey(self):
        return self.filesKey(keyName="tspecNewFiles")
    
    def filesKey(self, keyName="tspecFiles"):
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
                filebase)
        
    def _expose(self, type, exptime=None, extra=''):
        """ Start a single exposure. Requires several self. variables. """
         
        self.rawpath = self.genRawfileName(self.cmd)
        cb = tspecCB(None, self.sequence, self, type, debug=2)
        if exptime != None:
            exptimeArg = "time=%s" % (exptime)
        else:
            exptimeArg = ''
            
        #self.cmd.warn('debug=%s' % (CPL.qstr('firing off exposure callback to %s' % (self.rawpath))))
        r = self.callback("tspec", "expose %s %s basename=%s %s %s" % \
                          (type, exptimeArg, self.rawpath, self.commentArg, self.geometryString),
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

        cb = tspecCB(cmd, None, self, "stop", failOnFail=False, debug=2)
        self.callback("tspec", "expose stop",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def abort(self, cmd, **argv):
        """ Stop the current exposure immediately, and DISCARD the data. """

        cb = tspecCB(cmd, None, self, "abort", failOnFail=False, debug=2)
        self.callback("tspec", "expose abort",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def pause(self, cmd, **argv):
        """ Pause the current exposure. """

        cb = tspecCB(cmd, None, self, "pause", failOnFail=False, debug=2)
        self.callback("tspec", "expose pause",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def resume(self, cmd, **argv):
        """ Resume the current exposure. """

        if self.state != "paused":
            cmd.fail("text='can only resume paused exposures'")
            return

        cb = tspecCB(cmd, None, self, "resume", failOnFail=False, debug=2)
        self.callback("tspec", "expose resume",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)

        
        
