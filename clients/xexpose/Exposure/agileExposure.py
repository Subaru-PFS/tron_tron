>import os
import socket
import time

import CPL
import Parsing
import Exposure

class agileCB(Exposure.CB):
    """ Encapsulate a callback from the various AGILE commands.
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
        self.firstExposure = True
        
    def cbDribble(self, res):
        """ Handle per-line command replies.
        """

        if self.debug > 0:
            CPL.log("agileCB.cbDribble", "res=%s" % (res))
        try:
            # Check for new exposureState:
            newStateRaw = res.KVs.get('expStatus', None)
            if not newStateRaw:
                Exposure.CB.cbDribble(self, res)
                return
            try:
                self.exposure.cmd.warn('debug=%s' % (CPL.qstr("newstateRaw:%s:" % (newStateRaw))))
                newState,expType,expTime,currExpNum,numExpReq,begTimestamp,totDuration,remDuration = newStateRaw
                length = float(totDuration) ### Fixme CPL
                self.exposure.cmd.warn('debug=%s' % (CPL.qstr("newstate:%s,%0.2f" % (newState,length))))
            except:
                CPL.log('dribble', 'exposureState barf1 = %s' % (e))
                
            if newState == 'integrating':
                self.exposure.integrationStarted()
            elif newState == 'aborted':
                self.exposure.finishUp(aborting=True)
            elif newState == 'done':
                if currExpNum == numExpReq:
                    self.exposure.finishUp()
                    
            CPL.log('agileCB.cbDribble', "newstate=%s seq=%s what=%s" % (newState, self.sequence,self.what))
            # self.exposure.cmd.warn('debug=%s' % (CPL.qstr("setting newstate:%s,%0.2f" % (newState,length))))
            self.exposure.setState(newState, length)
        except Exception, e:
            CPL.log('dribble', 'exposureState barf = %s' % (e))
        
        Exposure.CB.cbDribble(self, res)

class agileExposure(Exposure.Exposure):
    def __init__(self, actor, seq, cmd, path, expType, **argv):
        Exposure.Exposure.__init__(self, actor, seq, cmd, path, expType, **argv)

        # Look for AGILE-specific options & arguments.
        #
        opts, notMatched, leftovers = cmd.match([('time', float),
                                                 ('comment', Parsing.dequote),
                                                 ('window',str),
                                                 ('bin',str),
                                                 ('overscan',str),
                                                 ('n',int)])

        self.comment = opts.get('comment', None)
        self.commentArg = ""
        if self.comment != None:
            self.commentArg = 'comment=%s ' % (CPL.qstr(self.comment))

        if expType in ("object", "dark", "flat"):
            try:
                self.expTime = opts['time']
            except:
                raise Exception("%s exposures require a time argument" % (expType))

        self.instArgString = self.parseInstArgs(opts)
        self.rawDir = ('/export/images/forTron/agile')
        self.reserveFilenames()

    def run(self):
        """ Call the real exposure method. """

        self.__class__.__dict__[self.expType](self)
        
    def parseInstArgs(self, opts):
        """ """
  
        instArgs = []
        if 'window' in opts:
            instArgs.append("window=%s" % (opts['window']))
        if 'bin' in opts:
            instArgs.append("bin=%s" % (opts['bin']))
        if 'overscan' in opts:
            instArgs.append("overscan=%s" % (opts['overscan']))
        if 'n' in opts:
            instArgs.append("n=%s" % (opts['n']))

        return " ".join(instArgs)
    
    def reserveFilenames(self):
        """ Reserve filenames, and set .basename.

        """

        self.pathParts = self.path.getFilenameAsDict(keepPath=True)

    def integrationStarted(self):
        """ Called when the integration is _known_ to have started. """

        if self.alreadyStarted:
            return
        self.alreadyStarted = True
        
        outfile = self.pathParts['fullPath']
        if self.debug > 2:
            self.cmd.warn("debug='starting agile FITS header to %s'" % (outfile))

        cmdStr = 'start agile' % (outfile)
        if self.comment:
            cmdStr += ' comment=%s' % (CPL.qstr(self.comment))
        # self.callback('fits', cmdStr)
        
    def finishUp(self, aborting=False):
        """ Clean up and close out the FITS files. """

        CPL.log("agile.finishUp", "state=%s" % (self.state))
        CPL.log('agileExposure', "finishing from rawfile=%s" % (self.rawpath))

        return
    
        if aborting:
            self.callback('fits', 'abort agile')
        else:
            self.callback('fits', 'finish agile infile=%s' % (self.rawpath))

    def genPathArgs(self, cmd):
        """ Generate a filename for the ICC to write to.

        Returns:
           filename  - a filename which is known not to exist now.
        """

        return "name=%(name) seq=%(seq) places=%(places)" % self.pathParts
    
    def lastFilesKey(self):
        return self.filesKey(keyName="agileFiles")
    
    def newFilesKey(self):
        return self.filesKey(keyName="agileNewFiles")
    
    def filesKey(self, keyName="agileFiles"):
        """ Return a fleshed out key variable describing our files.

        We return all the parts separately, in a form that can be
        handed to os.path.join(), at least on another Unix box.
        
        """
        
        filebase = self.pathParts['fullName']
        userDir = self.pathParts['userDir']
        if userDir != '':
            userDir += os.sep
            
        return "%s=%s,%s,%s,%s,%s,%s" % \
               (keyName,
                CPL.qstr(self.cmd.cmdrName),
                CPL.qstr('hub35m.apo.nmsu.edu'),
                CPL.qstr(self.pathParts['rootDir'] + os.sep),
                CPL.qstr(self.pathParts['programDir'] + os.sep),
                CPL.qstr(userDir),
                filebase)
        
    def _expose(self, type, exptime=None, extra=''):
        """ Start a single exposure. Requires several self. variables. """
         
        self.pathString = self.genPathArgs(self.cmd)
        cb = agileCB(None, self.sequence, self, type, debug=2)
        if exptime != None:
            exptimeArg = "time=%s" % (exptime)
        else:
            exptimeArg = ''
            
        # self.cmd.warn('debug=%s' % (CPL.qstr('firing off exposure callback to %s' % (self.rawpath))))
        r = self.callback("agile", "expose %s %s %s %s %s" % \
                          (type, exptimeArg, self.pathString, self.commentArg, self.instArgString),
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

        cb = agileCB(cmd, None, self, "stop", failOnFail=False, debug=2)
        self.callback("agile", "expose stop",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def abort(self, cmd, **argv):
        """ Stop the current exposure immediately, and AGILECARD the data. """

        cb = agileCB(cmd, None, self, "abort", failOnFail=False, debug=2)
        self.callback("agile", "expose abort",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def pause(self, cmd, **argv):
        """ Pause the current exposure. """

        cb = agileCB(cmd, None, self, "pause", failOnFail=False, debug=2)
        self.callback("agile", "expose pause",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def resume(self, cmd, **argv):
        """ Resume the current exposure. """

        if self.state != "paused":
            cmd.fail("text='can only resume paused exposures'")
            return

        cb = agileCB(cmd, None, self, "resume", failOnFail=False, debug=2)
        self.callback("agile", "expose resume",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)

        
        
