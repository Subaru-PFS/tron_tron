import os
import socket
import time

import CPL
import Parsing
import client
import Exposure

from fitscore import InstFITS

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
            length = 0.0
            try:
                newState,expType,expTime,currExpNum,numExpReq,begTimestamp,totDuration,remDuration,name = newStateRaw
                length = float(remDuration)
                name = eval(name)
            except Exception, e:
                CPL.log('dribble', 'exposureState barf1 = %s' % (e))

            #if newState == 'integrating':
            if newState in ('integrating', 'flushing'):
                self.exposure.integrationStarted()
                # newState = 'integrating'
            elif newState == 'aborted':
                self.exposure.finishUp(aborting=True)
            elif newState == 'expDone':
                self.exposure.finishUp(name=name)
            elif newState == 'done':
                pass
            else:
                self.exposure.cmd.warn('debug=%s' % (CPL.qstr("ignoring unknown newstate:%s,%0.2f" % (newState, length))))
                return
                
            CPL.log('agileCB.cbDribble', "newstate=%s seq=%s what=%s" % (newState, self.sequence, self.what))
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
                                                 ('gain',str),
                                                 ('readrate',str),
                                                 ('extsync',str),
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
        self.reserveFilenames()
        self.dummyCardPrefix = 'dumb' # Prefix for the cards we ask the ICC to reserve.
        self.dummyCardCnt = 50 # How many FITS cards we ask the ICC to reserve.
        
    def run(self):
        """ Call the real exposure method. """

        self.__class__.__dict__[self.expType](self)
        
    def parseInstArgs(self, opts):
        """ """
  
        instArgs = []
        for extra in ('window','bin','overscan','n','gain','readrate','extsync'):
            if extra in opts:
                if extra == 'gain' and opts[extra] == 'medium':
                    opts[extra] = 'med'
                instArgs.append("%s=%s" % (extra, opts[extra]))

        return " ".join(instArgs)
    
    def reserveFilenames(self):
        """ Reserve filenames, and set .basename.

        """

        self.pathParts = self.path.getFilenameAsDict()

    def integrationStarted(self):
        """ Called when the integration is _known_ to have started. """

        if self.alreadyStarted:
            return
        self.alreadyStarted = True
        
        outfile = self.pathParts['fullPath']
        if self.debug > 2:
            self.cmd.warn("debug='starting agile FITS header to %s'" % (outfile))

        cmdStr = 'start agile %s' % (outfile)
        if self.comment:
            cmdStr += ' comment=%s' % (CPL.qstr(self.comment))
        # self.callback('fits', cmdStr)

    def fiddleFITS(self, name):
        try:
            a = InstFITS('agile', self.cmd, debug=True, comment=self.comment, isImager=True)
            a.start(self.cmd)
            a.finishInto(self.cmd, name, self.dummyCardPrefix, maxCount=self.dummyCardCnt)
        except Exception, e:
            self.cmd.warn('debug=%s' % (CPL.qstr(e)))
    
    def finishUp(self, name=None, aborting=False):
        """ Clean up and close out the FITS files. """

        CPL.log("agile.finishUp", "state=%s" % (self.state))
        try:
            stat = os.stat(name)
            size = stat.st_size
        except:
            stat=None
            size=0
        self.cmd.warn("debug=%s" % (CPL.qstr("finishing file %s with size=%s" % (name,size))))

        if not aborting:
            self.fiddleFITS(name)
        self.sequence.nextInSequence()
        self.reserveFilenames()

        return
    
    def genPathArgs(self, cmd):
        """ Generate a filename for the ICC to write to.

        Returns:
           filename  - a filename which is known not to exist now.
        """

        #cmd.warn("debug pathParts: %s" % (CPL.qstr(self.pathParts)))
        baseName = 'name=%s' % (CPL.qstr(os.path.join(self.pathParts['fullDir'], self.pathParts['name'])))
        
        return baseName + ' seq=%(seq)s places=%(places)s' % (self.pathParts)
    
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
         
        ret = client.call('keys','getFor=tcc')
        self.pathString = self.genPathArgs(self.cmd)
        # For testing on a different machine
        # testPathString = self.pathString.replace('/export/images/','/export/test-images/',1)
        
        cb = agileCB(None, self.sequence, self, type, debug=2)
        if exptime != None:
            exptimeArg = "time=%s" % (exptime)
        else:
            exptimeArg = ''
            
        # self.cmd.warn('debug=%s' % (CPL.qstr('firing off exposure callback to %s' % (self.rawpath))))
        r0 = client.call('agile', 'addCards %s,%d' % (self.dummyCardPrefix, self.dummyCardCnt),
                         cid=self.actor.cidForCmd(self.cmd))
        r = self.callback("agile", "expose %s %s %s %s" % \
                          (type, exptimeArg, self.pathString, self.instArgString),
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

        cmd.fail("text='agile cannot (yet) pause exposure sequences'")
        return

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

        
        
