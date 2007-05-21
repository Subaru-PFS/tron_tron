import os
import socket

import CPL
import Parsing
import Exposure

class spicamCB(Exposure.CB):
    """ Encapsulate a callback from the various SPICAM commands.
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
            CPL.log("spicamCB.cbDribble", "res=%s" % (res))
        try:
            # Check for new exposureState:
            newState = res.KVs.get('exposureState', None)
            
            # Guess at their length (this is for SPICAM only)
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
                
                CPL.log('spicamCB.cbDribble', "newstate=%s seq=%s" % (newState, self.sequence))
                self.exposure.setState(newState, length)
        except Exception, e:
            CPL.log('dribble', 'exposureState barf = %s' % (e))
        
        Exposure.CB.cbDribble(self, res)
        

class spicamExposure(Exposure.Exposure):
    def __init__(self, actor, seq, cmd, path, expType, **argv):
        Exposure.Exposure.__init__(self, actor, seq, cmd, path, expType, **argv)

        # Look for SPICAM-specific options & arguments.
        #
        opts, notMatched, leftovers = cmd.match([('time', float),
                                                 ('comment', Parsing.dequote)])

        # Fetch the camera list. Default to empty, which means both cameras.
        #
        self.cameras = ""
            
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

        """

        self.pathParts = self.path.getFilenameInParts(keepPath=True)

    def _basename(self):
        return os.path.join(*self.pathParts)

    def lastFilesKey(self):
        return self.filesKey(keyName="spicamFiles")
    
    def newFilesKey(self):
        return self.filesKey(keyName="spicamNewFiles")
    
    def filesKey(self, keyName="spicamFiles"):
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
                filebase)
        
    def bias(self):
        """ Start a single bias. Requires several self. variables. """
         
        cb = spicamCB(None, self.sequence, self, "bias", debug=2)
        r = self.callback("spicam", "expose bias basename=%s %s" % \
                          (self._basename(), self.commentArg),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
    def object(self):
        """ Start a single object exposure. Requires several self. variables. """

        cb = spicamCB(None, self.sequence, self, "object", debug=2)
        r = self.callback("spicam", "expose object time=%s basename=%s %s" % \
                          (self.expTime, self._basename(), self.commentArg),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
    def flat(self):
        """ Start a single flat exposure. Requires several self. variables. """

        cb = spicamCB(None, self.sequence, self, "flat", debug=2)
        r = self.callback("spicam", "expose flat time=%s basename=%s %s" % \
                          (self.expTime, self._basename(), self.commentArg),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
    def dark(self):
        """ Start a single dark. Requires several self. variables. """

        cb = spicamCB(None, self.sequence, self, "dark", debug=2)
        r = self.callback("spicam", "expose dark time=%s basename=%s %s" % \
                          (self.expTime, self._basename(), self.commentArg),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
    def stop(self, cmd, **argv):
        """ Stop the current exposure: cause it to read out immediately, and save the data. """

        cb = spicamCB(cmd, None, self, "stop", failOnFail=False, debug=2)
        self.callback("spicam", "expose stop",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def abort(self, cmd, **argv):
        """ Stop the current exposure immediately, and SPICAMCARD the data. """

        cb = spicamCB(cmd, None, self, "abort", failOnFail=False, debug=2)
        self.callback("spicam", "expose abort",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def pause(self, cmd, **argv):
        """ Pause the current exposure. """

        cb = spicamCB(cmd, None, self, "pause", failOnFail=False, debug=2)
        self.callback("spicam", "expose pause",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)
        
    def resume(self, cmd, **argv):
        """ Resume the current exposure. """

        if self.state != "paused":
            cmd.fail("spicamTxt", "can only resume paused exposures")
            return

        cb = spicamCB(cmd, None, self, "resume", failOnFail=False, debug=2)
        self.callback("spicam", "expose resume",
                      callback=cb.cbDribble, responseTo=cmd, dribble=True)

        
        
