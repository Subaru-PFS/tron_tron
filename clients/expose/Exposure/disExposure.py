import os
import socket

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
            newState = res.KVs.get('exposureState', None)
            
            # Guess at their length (this is for DIS only)
            if newState != None:
                newState = eval(newState, {}, {})
                length = 0.0
                if newState == 'reading':
                    # Use the instrument's length guess if it is available.
                    length = 45.0
                    t = res.KVs.get('readoutTime', None)
                    if t != None:
                        try:
                            length = float(t)
                        except:
                            pass
                
                CPL.log('disCB.cbDribble', "newstate=%s seq=%s" % (newState, self.sequence))
                self.exposure.setState(newState, length)
        except Exception, e:
            CPL.log('dribble', 'exposureState barf = %s' % (e))
        
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

        self.reserveFilenames()

    def reserveFilenames(self):
        """ Reserve filenames, and set .basename.

        The trick here is that DIS appends "r.fits" and "b.fits", so we need to strip off the suffix
        
        """

        parts = list(self.path.getFilenameInParts(keepPath=True))
        basename = os.path.splitext(parts[-1])[0]
        parts[-1] = basename
        
        self.pathParts = parts

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
                CPL.qstr('tycho.apo.nmsu.edu'),
                CPL.qstr(self.pathParts[0] + os.sep),
                CPL.qstr(self.pathParts[1] + os.sep),
                CPL.qstr(userDir),
                blueFile, redFile)
        
    def bias(self):
        """ Start a single bias. Requires several self. variables. """
         
        cb = disCB(None, self.sequence, self, "bias", debug=2)
        r = self.callback("dis", "expose bias basename=%s %s %s" % \
                          (self._basename(), self.cameras, self.commentArg),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
    def object(self):
        """ Start a single object exposure. Requires several self. variables. """

        cb = disCB(None, self.sequence, self, "object", debug=2)
        r = self.callback("dis", "expose object time=%s basename=%s %s %s" % \
                          (self.expTime, self._basename(), self.cameras, self.commentArg),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
    def flat(self):
        """ Start a single flat exposure. Requires several self. variables. """

        cb = disCB(None, self.sequence, self, "flat", debug=2)
        r = self.callback("dis", "expose flat time=%s basename=%s %s %s" % \
                          (self.expTime, self._basename(), self.cameras, self.commentArg),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
    def dark(self):
        """ Start a single dark. Requires several self. variables. """

        cb = disCB(None, self.sequence, self, "dark", debug=2)
        r = self.callback("dis", "expose dark time=%s basename=%s %s %s" % \
                          (self.expTime, self._basename(), self.cameras, self.commentArg),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
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

        
        
