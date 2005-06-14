import os
import socket

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

                if maybeNewState in ('flushing', 'reading', 'paused'):
                    newState = maybeNewState
                elif maybeNewState == 'integrating':
                    newState = maybeNewState
                    # self.exposure.integrationStarted()
                elif maybeNewState == 'aborted':
                    CPL.log("nicfps.dribble", "aborted what=%s newState=%s" % (self.what, maybeNewState))
                    if self.exposure.aborting:
                        newState = "aborted"
                    else:
                        newState = "done"
                        # self.exposure.finishUp()
                elif maybeNewState == 'done':
                    newState = maybeNewState
                    # self.exposure.finishUp()

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

        self.reserveFilenames()

    def reserveFilenames(self):
        """ Reserve filenames, and set .basename.

        """

        self.pathParts = self.path.getFilenameInParts(keepPath=True)

    def _basename(self):
        return os.path.join(*self.pathParts)

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
                CPL.qstr('tycho.apo.nmsu.edu'),
                CPL.qstr(self.pathParts[0] + os.sep),
                CPL.qstr(self.pathParts[1] + os.sep),
                CPL.qstr(userDir),
                CPL.qstr(self.pathParts[-1]))
        
    def bias(self):
        """ Start a single bias. Requires several self. variables. """
         
        cb = echelleCB(None, self.sequence, self, "bias", debug=2)
        r = self.callback("echelle", "expose bias diskname=%s %s" % \
                          (self._basename(), self.commentArg),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
    def object(self):
        """ Start a single object exposure. Requires several self. variables. """

        cb = echelleCB(None, self.sequence, self, "object", debug=2)
        r = self.callback("echelle", "expose object time=%s diskname=%s %s" % \
                          (self.expTime, self._basename(), self.commentArg),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
    def flat(self):
        """ Start a single flat exposure. Requires several self. variables. """

        cb = echelleCB(None, self.sequence, self, "flat", debug=2)
        r = self.callback("echelle", "expose flat time=%s diskname=%s %s" % \
                          (self.expTime, self._basename(), self.commentArg),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
    def dark(self):
        """ Start a single dark. Requires several self. variables. """

        cb = echelleCB(None, self.sequence, self, "dark", debug=2)
        r = self.callback("echelle", "expose dark time=%s diskname=%s %s" % \
                          (self.expTime, self._basename(), self.commentArg),
                          callback=cb.cbDribble, responseTo=self.cmd, dribble=True)
        
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

        
        
