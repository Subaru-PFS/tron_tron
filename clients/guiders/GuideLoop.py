__all__ = ['GuideLoop']

import math
import os
import time
import threading

import pyfits

import client
import CPL
import GuideFrame
import MyPyGuide
import Parsing

class GuideLoop(object):
    def __init__(self, controller, tcc, cmd, tweaks):
        """ Encapsulate a single guiding loop. 

        Args:
            control   - the controlling object, which we let know when we finish.
            tcc       - the object which wraps the tcc for us.
            cmd       - the controllng Command.
            tweaks    - a dictionary of variables controlling our behavior.

        There are several guiding modes, named in the guideMode keyword:
          idle      - before we start.
          manual    - an exposure loop only.
          field     - actively guiding using field stars.
          boresight - actively guiding by moving the star closest to
                      the boresight to the boresight.
          acquire   - take one image and generate the star positions.
          centerOn  - move a given pixel position to the boresight.

        If there is no loop, one is started.
        If there is a loop, some transitions between modes can be taken:
          manual -> boresight
          manual -> field
          manual: centerOn
          
          field -> manual
          field: change stars

          boresight -> manual
          boresight: centerOn (mode changes to manual)
          
        """

        self.controller = controller
        self.tcc = tcc
        self.cmd = cmd
        self.tweaks = tweaks

        self.exposing = False

        # flag to synchronize moves with start exposure
        # 20080910 - FRS guider hangups
        self.moving = threading.Event()
        self.moving.set()

        self.cmd.warn('debug="new loop"')
        
        # This controls whether the loop continues or stops, and gives the
        # guider keyword value.
        self.state = 'starting'
        self.action = ''
        self.mode = 'idle'
        
        # How many times we have failed to find a star.
        self.retries = 0
        
        # The 'reference' PVT that we guiding on or to.
        self.refPVT = None
        self.newRefStars = None
        self.currentFrame = None
        
        # If we are "guiding" on a file sequence, track the sequence here.
        self.trackFilename = None
        
        self._initTrailing()

        # We listen for changes in TCC keywords that indicate that a guider frame
        # may not be valid, and guess when an uncomputed offset will be done.
        #
        self.telHasBeenMoved = False
        self.offsetWillBeDone = 0.0
        self.waitingForSlewEnd = False
        self.invalidLoop = False
        
        self.dontCareAboutSlews = False

        self.centerOn = None

        self.tcc.connectToMe(self)

    def __del__(self):
        pass
        
    def __str__(self):
        return "GuideLoop(guiding=%s)" % (self.state)

    def statusCmd(self, cmd, doFinish=True):
        """ Generate all our status keywords. """

        self.genTweaksKeys(cmd)
        self.genStateKey(cmd)

        if doFinish:
            cmd.finish()

    def genTweaksKeys(self, cmd):
        cmd.respond("fsActThresh=%0.1f; fsActRadMult=%0.1f; centActRadius=%0.1f" % \
                    (self.tweaks['thresh'],
                     self.tweaks['radMult'],
                     self.tweaks['cradius']))
        cmd.respond("retryCnt=%d; restart=%s" % (self.tweaks['retry'],
                                                 CPL.qstr(self.tweaks['restart'])))
    def genChangedTweaks(self, cmd):
        cmd.respond("fsActThresh=%0.1f; fsActRadMult=%0.1f; centActRadius=%0.1f" % \
                    (self.tweaks['thresh'],
                     self.tweaks['radMult'],
                     self.tweaks['cradius']))
        
    def tweakCmd(self, cmd, newTweaks):
        """ Adjust the running guide loop.

        Args:
            cmd       - the command that is changing the tweaks.
            newTweaks - a dictionary containing only the changed variables.

        The loop sends a copy of the tweaks dictionary down to the
        exposure and offset callbacks, and uses those copies when it
        runs. But when a new iteration is started, the new tweaks will
        apply.  It would be bad to change, say, the binning or
        windowing between the request for the exposure and the
        calculations of the offset.  """

        CPL.log('GuideLoop', 'newtweaks=%s' % (newTweaks))
        
        self.tweaks.update(newTweaks)
        self._setupLoop(cmd, doRun=False)

    def run(self):
        """ Actually start the guide loop. Called from the outside. """

        if not self.isRightPort():
            return

        self.genTweaksKeys(self.cmd)
        self._setupLoop(self.cmd, doRun=True)
        
    def acceptTweaks(self):
        pass

    def genStateKey(self, cmd=None, mode=None, state=None, action=None):
        if cmd == None:
            cmd = self.cmd

        if mode != None:
            self.mode = mode
        if state != None:
            self.state = state
        if action != None:
            self.action = action

        if state in ('off', 'stopping'):
            self.invalidLoop = True
            
        cmd.respond('guideMode=%s; guideState=%s,%s' % \
                    (CPL.qstr(self.mode),
                     CPL.qstr(self.state),
                     CPL.qstr(self.action)))
        
    def telescopeHasMoved(self, computed, newField=False, how=None):
        """ The telescope has begun moving.

        This is what self.tcc calls when it decides that a move has started.

        Args:
           computed   - True if a slew or a computed offset.
           newField   - True is a slew.
           how        - possibly interesting human-readable comment.

        """

        self.cmd.warn('debug="telescopeHasMoved mode=%s computed=%s newField=%s how=%s"' % \
                 (self.mode, computed, newField, how))
        
        # If we are just exposing, ignore motion.
        if self.mode == 'centerUp':
            return

        # Alert any other threads that they should bail out.
        self.invalidLoop = True

        # Computed offsets are asynchronous: we need to wait for
        # a telescopeSlewIsDone call.
        if computed:
            self.telHasBeenMoved = how
            
            # Check this -- CPL
            if newField:
                self.cmd.warn('text="Object or instrument has been changed. Stopping guide loop."')
                self.restartGuiding()
            else:
                self.waitingForSlewEnd = True
        else:
            # If this is an uncomputed offset, synchronize the move end with
            # the guide loop, and set when the offset is done (settled).
            endTime = time.time() + CPL.cfg.get('telescope', 'offsetSettlingTime')
            if endTime > self.offsetWillBeDone:
                self.offsetWillBeDone = endTime
            self.moving.set()
                
    def telescopeHasHalted(self):
        """ The telescope has halted.

        Called by self.tcc when an axis is halted.
        """

        self.cmd.warn('text="one or more axes are halted: stopping guide loop"')
        self.stop(self.cmd, doFinish=False)

    def telescopeSlewIsDone(self):
        """ The slew is finished, and we are tracking again.

        Called by self.tcc after a slew has finished.
        """
        
        self.cmd.warn('debug="telescopeSlewIsDone mode=%s waiting=%s"' % \
                 (self.mode, self.waitingForSlewEnd))

        if self.waitingForSlewEnd:
            self.waitingForSlewEnd = False
        else:
            self.cmd.warn('debug="possibly unexpected SlewEnd"')

        self._guideLoopTop()
    
    def cleanup(self):
        """ """

        # TUI generates the slewing ending sound when it sees the "stopping" state.
        # Force that now.
        if self.state != 'stopping':
            self.genStateKey(state='stopping', action='')
            
        self.genStateKey(state='off', action='')
        self.tcc.disconnectFromMe(self)
        
    def failGuiding(self, why):
        """ Stop guiding, 'cuz something went wrong.
        This must only be called when the loop has stopped.
        """

        self.invalidLoop = True
        self.cleanup()
        self.cmd.fail('text=%s' % (CPL.qstr(why)))
        self.controller.guideLoopIsStopped()

    def stopGuiding(self):
        """ Stop guiding, on purpose
        This must only be called when the loop has stopped.
        """

        self.invalidLoop = True
        self.cmd.respond('debug="in stopGuiding"')
        self.cleanup()
        self.cmd.finish()
        self.controller.guideLoopIsStopped()
        
    def retryGuiding(self):
        """ Called when the guide loop centroiding fails.
        """

        if self.retries < self.tweaks['retry']:
            self.retries += 1
            self.cmd.warn('noGuideStar; text="no star found; retrying (%d of %d tries)"' % \
                          (self.retries, self.tweaks['retry']))
        else:
            self.cmd.warn('noGuideStar; text="no star found after %d tries, switching to manual"' % \
                          (self.retries))
            self.genStateKey(mode='manual')
            
        self._guideLoopTop()

    def restartGuiding(self):
        """ Called when we have moved to a new field. """

        self.stopGuiding()

    def isRightPort(self):
        """ Decide whether we can see the sky. """
        
        # First, check whether we are in the right place:
        ret = client.call('tcc', 'show inst')
        instName = ret.KVs.get('Inst', 'unknown')
        portName = ret.KVs.get('InstPos', 'unknown')
        instName = Parsing.dequote(instName)
        portName = Parsing.dequote(portName)

        requiredInst = self.tweaks.get('requiredInst', 'undefined')
        requiredPort = self.tweaks.get('requiredPort', 'undefined')

        if requiredInst and instName.lower() != requiredInst.lower():
            self.failGuiding('The instrument must be %s, not %s' % (requiredInst,
                                                                    instName))
            return False

        if requiredPort and portName.lower() != requiredPort.lower():
            self.failGuiding('The instrument port must be %s, not %s' % (requiredPort,
                                                                         portName))
            return False

        return True

    def getMode(self, cmd, tweaks):
        pass
    
    def stop(self, cmd, doFinish=True):
        """ A way for the outside world to stop the loop.

        This merely sets a flag that other parts of the loop examine at appropriate times.
        """

        if self.state == 'stopping':
            cmd.warn('text="guide loop is already being stopped"')
            cmd.finish()
            return
        
        if doFinish:
            cmd.finish('text="stopping guide loop...."')
        else:
            cmd.respond('text="stopping guide loop...."')
        
        self.genStateKey(state='stopping')

    def checkSubframe(self):
        """ Optionally window around the boresight. """
        
        if self.tweaks.has_key('autoSubframe'):
            size = self.tweaks['autoSubframe']
            if size[0] == 0.0 and size[1] == 0.0:
                try:
                    del self.tweaks['window']
                except:
                    pass
                del self.tweaks['autoSubframe']
                return
            
            ctr = self.tcc.boresight()
            self.tweaks['window'] = (ctr[0]-size[0], ctr[1]-size[1],
                                     ctr[0]+size[0], ctr[1]+size[1])
        
    def _setupLoop(self, cmd, doRun=False):
        """ Set up or tweak the guide loop parameters.

        Examines parts of the .tweaks dictionary for several things:
           gstar=X,Y   - the position to start centroiding on.
        or:
           centerOn=X,Y  - the position of a star to move to the boresight.

        If neither is specified, run a findstars and guide on the "best" return.
        """

        CPL.log("_setupLoop", "tweaks=%s" % (self.tweaks))
        cmd.warn('debug="setup"')
        # Steps:
        #  1) Look for at-start offsets (centerOn=X,Y or gstar=X,Y
        #      if specified, use specified position to seed centroid()
        #      then move the result to the boresight.
        #
        
        #
        centerOn = cmd.argDict.get('centerOn')

        # Silly of me to use None for argument-less command options!

        # Need to allow several gstars!
        gstar = cmd.argDict.get('gstar')
        field = gstar or (cmd.argDict.get('field', 'nope') != 'nope')

        boresight = cmd.argDict.get('boresight', 'nope') != 'nope'
        manual = cmd.argDict.get('manual', 'nope') != 'nope'
        
        # A few command argument checks.
        if (boresight or centerOn) and field:
            if cmd == self.cmd:
                self.failGuiding('cannot specify both field and boresight guiding.')
            else:
                cmd.fail('text="cannot specify both field and boresight guiding."')
            return
        if (boresight or field) and manual:
            if cmd == self.cmd:
                self.failGuiding('cannot specify both manual and automatic guiding.')
            else:
                cmd.fail('text="cannot specify both manual and automatic guiding."')
            return
        if (boresight or centerOn) and self.controller.guiderType == 'gimage':
            if cmd == self.cmd:
                self.failGuiding('cannot guide to the boresight of an offset guider.')
            else:
                cmd.fail('text="cannot guide to the boresight of an offset guider."')
            return

        if manual:
            # I can't do this until I re-examine windowing.
            # self.checkSubframe()

            self.mode = 'manual'

        elif boresight:
            # Simply start nudging the object nearest the boresight to the boresight
            #

            # I can't do this until I re-examine windowing.
            # self.checkSubframe()

            self.mode = 'boresight'

        elif field:
            if gstar:
                # if "gstar" is specified, use that as the guide star.
                #
                try:
                    seedPos = self.controller.parseCoord(gstar)
                except Exception, e:
                    CPL.tback('guideloop._doGuide', e)
                    self.failGuiding(e)
                    self.tweaksSem.release()
                    return
                
                gstars = [seedPos]
            else:
                gstars = []

            # Arrange for the guide loop to switch guide stars
            self.newRefStars = gstars
            self.mode = 'field'
        #else:
        #    cmd.fail('text="FELL OFF THE LOOP IN GuideLoop.setupLoop!"')
            
        # if "centerOn" is specified, define the position to move to. This is
        # independant of whether we are or will be guiding.
        if centerOn:
            if self.mode == 'field':
                cmd.fail('text="cannot move an object to the boresight while field guiding (yet)."')
                return
            
            # If we are not in a manual or boresight loop, set a meaningful mode.
            if self.mode == 'idle':
                self.genStateKey(mode='centerUp')
                
            try:
                seedPos = self.controller.parseCoord(centerOn)
            except Exception, e:
                self.failGuiding('could not parse the centerOn position: %s.' % (e))
                self.tweaksSem.release()
                return

            # This is only read in guideLoopTop, so is safe to change without
            # invalidating the loop or going through a semaphore.
            self.centerOn = seedPos

            cmd.warn('debug="setup centerOn=%s"' % (seedPos))
        if doRun:
            self._guideLoopTop()

    def _guideLoopTop(self):
        """ The "top" of the guiding loop.

        This is
           a) one place where the loop gets stopped and
           b) where the loop gets deferred should an immediate move (an uncomputed offset)
           have been started.

        All tweaks and states are assumed to have been sanity checked and be consistent.
        """

        self.cmd.warn('debug="guideLoopTop waiting=%s mode=%s state=%s centeron=%s"' % \
                      (self.waitingForSlewEnd, self.mode, self.state, self.centerOn))

        # Some part of the loop or an external command has declared us finished.
        if self.state == 'off':
            return
        if self.state == 'stopping':
            self.stopGuiding()
            return

        # If we are starting up a new loop, announce ourselves.
        if self.state == 'starting':
            self.genStateKey(state='on')
            
        # Exposure in progress. Go away: the exposure callback will call us again.
        if self.exposing:
            self.genStateKey(action='deferring')
            self.cmd.warn('text="waiting for old exposure to finish"')
            return

        # The next expose can be cancelled at any time.  The moves can 
        # not cancel the exposure, but, are synchronized here by a flag.  
        # Go ahead and take the image, and after the image is done, call back _centerUp(), 
        # and decide there if to toss the image.  
        # _guideLoopTop() is controlled only by the state flags. The control logic is higher up.
        self.invalidLoop = False

        # Offset in progress. Go away: the offset callback will call us again.
        # To the user, when they click on guiding during a slew, the guide loop
        # will keep shutting off.  This catches that.  It seems that this should
        # go higher up into the control logic, i.e. caught earlier so we
        # don't need this test here.
        if self.waitingForSlewEnd:
            self.genStateKey(action='deferring')
            self.cmd.warn('text="waiting for offset to finish"')
            return

        # Wait for the end of an uncomputed offset.
        # 20080910 - FRS guider hangups
        if self.moving.isSet() == 0:
            diff = CPL.cfg.get('telescope', 'offsetSettlingTime')

            CPL.log('gcam',
                    'waiting offset guider frame to finish')
            self.genStateKey(action='deferring')
            self.moving.wait(5)

        if self.moving.isSet() == 0:
            self.cmd.warn('text="guider loop waiting for offset timed out."')

        elif self.offsetWillBeDone > 0.0:
            diff = self.offsetWillBeDone - time.time()

            if diff > 0.0:
                CPL.log('gcam',
                        'deferring guider frame for %0.2f seconds to allow immediate offset to finish' % (diff))
                self.genStateKey(action='deferring')
                self.cmd.warn('text="waiting %0.2fs for offset to finish"' % (diff))
                time.sleep(diff)        # Yup. Better be short, hunh?
            self.offsetWillBeDone = 0.0

        # Make any requested centering offset asynchronously.  The offset will
        # command will complete and call guideLoopTop().  By then, the move
        # flag is cleared, and guideLoopTop() will have to wait for the move
        # to be done.
        if self.centerOn:
            # If we are centering, then, skip this expose.  When centering is
            # done, the _doneOffsetting() callback will restart the guide loop.
            return self.centerUp()

        # Launch new expose-measure-(offset) loop.
        self.genStateKey(action='exposing')
        self._doExpose(self._handleGuiderFrame)
        
    def _doExpose(self, callback):
        """ Arrange for an exposure, finished by a given callback. """

        self.exposing = True
        CPL.log('doExpose', 'tweaks=%s' % (self.tweaks))
        ret = self.controller.doCmdExpose(self.cmd, callback, 'expose', self.tweaks)
        if not ret:
            self.failGuiding('exposure failed')
            return
    
    def centerUp(self):
        """ Synchronously move a given pixel to the boresight. """
        
        seedPos = self.centerOn
        if not seedPos:
            self.cmd.warn('text="centerUp called without a specified star position."')
            return

        # Clear out the requested offset
        self.centerOn = None
        
        self.cmd.respond('text="offsetting object at (%0.1f, %0.1f) to the boresight...."' % \
                         (seedPos[0], seedPos[1]))
        try:
            refpos = self.tcc.getBoresight()
            try:
                imgFile = os.path.join('/export/images', self.tweaks['imgFile'])
                frame = GuideFrame.ImageFrame(self.controller.size)
                frame.setImageFromFITSFile(imgFile)
            except Exception, e:
                self.cmd.warn('text="%s"' % (CPL.qstr("could not read imgFile %s: %s" % \
                                                      (imgFile, e))))
                frame = GuideFrame.ImageFrame(self.controller.size)
            
            CCDstar = MyPyGuide.imgPos2CCDXY(seedPos, frame)
            self.cmd.warn('debug="CCDstar: (%0.1f, %0.1f) to refpos: (%0.1f, %0.1f); frame=%s"' %
                          (CCDstar.ctr[0], CCDstar.ctr[1], refpos[0], refpos[1], frame))
            
            cmdTxt, mustWait = self._genOffsetCmd(self.cmd, CCDstar,
                                                  frame, refpos,
                                                  offsetType='guide',
                                                  doScale=False)
            self.genStateKey(action='offsetting')

            # _doneOffsetting will restart the next guide loop.
            client.callback('tcc', cmdTxt, self._doneOffsetting,
                                 cid=self.controller.cidForCmd(self.cmd))
            self.moving.clear()
            return

            # Synchronous call, here. I just don't want do deal with another bit of
            # callback goo.
            ret = client.call('tcc', cmdTxt,
                              cid=self.controller.cidForCmd(self.cmd))
            if mustWait:
                time.sleep(CPL.cfg.get('telescope', 'offsetSettlingTime'))
                self.offsetWillBeDone = 0.0
        except Exception, e:
            CPL.tback('guideloop._firstExposure-2', e)
            self.failGuiding(e)
            return

        if not ret.ok:
            self.failGuiding('centering offset failed')
            return

    def defineRefStars(self, gstars, procFile, frame, tweaks):
        """ For field guiding, define the refPVT which we guide to.

        There are many limitations:
          - should be able to guide on multiple objects.
          - should be able to use a given image filename.
          - should be able to decide whether to centroid before using the given coordinates.

        Returns:
          bool   - True if successful, False if not.
        """
        
        if gstars:
            # I am not prepared to guide on multiple stars: need matching code.
            #
            seedPos = gstars[0]

            CPL.log('GuideLoop', '1st exp gstar=%s' % (seedPos))

            # We centroid on the given position in a current image file before using it. 
            try:
                star = MyPyGuide.centroid(self.cmd, procFile,
                                          frame, seedPos, tweaks)
                if not star:
                    self.failGuiding('no star found near (%0.1f, %0.1f)' % \
                                     (seedPos[0], seedPos[1]))
                    return False
            except Exception, e:
                CPL.tback('guideloop._firstExposure-3', e)
                self.failGuiding(e)
                return False
            CPL.log('GuideLoop', '1st exp star=%s' % (star))
        else:
            # otherwise use the "best" object as the guide star.
            # We could extend to several...
            try:
                stars = MyPyGuide.findstars(self.cmd, procFile,
                                            frame, tweaks)
                if not stars:
                    self.failGuiding("no stars found")
                    return False
            except:
                pass
            star = stars[0]
            
        CCDstar = MyPyGuide.star2CCDXY(star, frame)

        # OK, we have a star, convert its coordinates and get a PVT.

        try:
            CPL.log('GuideLoop', '1st exp ccdstar=%s' % (CCDstar))
            self.refPVT = self.tcc.frame2ICRS(CCDstar.ctr)
            CPL.log('GuideLoop', '1st exp refPVT=%s' % (self.refPVT))
            
            # Per Russell: make sure to zero out the velocities on the ICRS reference
            # position.
            #
            self.refPVT[1] = self.refPVT[4] = 0.0
        except Exception, e:
            self.failGuiding('could not establish the guidestar coordinates: %s' % (e))
            return False

        return True


    def scaleOffset(self, star, diffPos):
        """ Scale the effective offset.

        Args:
            star          - star info, including s.ctr and error estimates
            diffPos       - the original offset.

        We use tweaks['fitErrorScale'], which is a list of thresh0,scale0,...threshN,scaleN
        pairs. If the individual coordinate errors are less than a given threshold, scale
        the offset by the corresponding scale.

        Note that the star errors are in pixels, while the scales and diffPos are in arcseconds.
        
        Think about a dead zone, or a scaling function that decreases close to the boresight.
        """

        # Gauge star quality somehow.


        # Convert to axis arcsec
        fitErrors = (abs(star.err[0] * 3600.0 / self.tcc.imScale[0]),
                     abs(star.err[1] * 3600.0 / self.tcc.imScale[1]))

        scales = self.tweaks['fitErrorScale']
                       
        xfitFactor = 0.0
        xoffset = 0.0
        for scale in scales:
            if fitErrors[0] < scale[0]:
                xfitFactor = scale[1]
                xoffset = diffPos[0] * xfitFactor
                break

        yfitFactor = 0.0
        yoffset = 0.0
        for scale in scales:
            if fitErrors[1] < scale[0]:
                yfitFactor = scale[1]
                yoffset = diffPos[1] * yfitFactor
                break

        return [xoffset, yoffset]
               

    def _initTrailing(self):
        """ Initialize toy test trailing for the Echelle. """

        self.trailingOffset = 0.0
        self.trailingLimit = 1.5 / (60*60)
        self.trailingStep = 0.5 / (60*60)
        self.trailingSkip = 1
        self.trailingDir = 1
        self.trailingN = 0

        self.doTrail = self.cmd.argDict.has_key('trail')
        
        
    def _getTrailOffset(self):
        """ Return the next (toy, test) trailing offset, in degrees. Unused placeholder. """

        if not self.doTrail:
            return [0.0, 0.0]
        
        # Move .trailingStep each offset we take. When we reach the end (.trailingLimit),
        # turn around.
        #
        if abs(self.trailingOffset) >= self.trailingLimit:
            self.trailingDir *= -1
            
        self.trailingOffset += self.trailingDir * self.trailingStep

        return [0.0, self.trailingOffset]

    def _getExpectedPos(self, t=None):
        """ Return the expected position of the guide star in GPos coordinates. """

        if self.mode == 'field':
            pvt = self.tcc.ICRS2Frame(self.tcc.PVT2pos(self.refPVT, t=t))
            pos = self.tcc.PVT2pos(pvt, t=t)
            if self.controller.guiderType == 'inst':
                pos = self.tcc.inst2pixels(pos)
            return pos
        else:
            return self.tcc.getBoresight(t)

    def diffSkyDegrees(self, p1, p2):
        """ Return p1 - p2, unwrapping the [0..360) range. """
        
        d = p1 - p2
        if d <= -180.0:
            d = - (d + 360.0)
            
        return d
        
    def _genOffsetCmd(self, cmd, star, frame, refGpos, offsetType='guide', doScale=True, fname=''):
        """ Generate the TCC offset command between the given star and refGpos
        
        Args:
            cmd        - the command that controls us.
            star       - the star that we want to move.
            frame      - the ImageFrame that star the embedded in.
            refGpos    - the GImage position to move to/towards
            offsetType - 'guide' or 'calibration'
            doScale    - if True, filter the offset according to self.tweaks

        Return:
            - the offset command string
            - whether the offset is uncomputed
        """

        # We know the boresight pixel .boresightPixel and the source pixel fromixel.
        #  - Convert each to Observed positions
        #
        now = time.time()
        refPVT = self.tcc.frame2Obs(refGpos)
        starPVT = self.tcc.frame2Obs(star.ctr)
        
        if not refPVT \
           or not starPVT \
           or None in refPVT \
           or None in starPVT:
            self.failGuiding("Could not convert a coordinate")
            return '', False

        # Optionally trail the star across or up&down the slit.
        #trailOffset = self._getTrailOffset()
        #refPos = [refPos[0] + trailOffset[0],
        #          refPos[1] + trailOffset[1]]
        
        #  - Diff the Observed positions
        #

        refPos = self.tcc.PVT2pos(refPVT, t=now)
        starPos = self.tcc.PVT2pos(starPVT, t=now)
        baseDiffPos = [self.diffSkyDegrees(starPos[0], refPos[0]), \
                       self.diffSkyDegrees(starPos[1], refPos[1])]

        if doScale:
            diffPos = self.scaleOffset(star, baseDiffPos)
        else:
            diffPos = baseDiffPos

        # Check whether we have been scaled out of existence.
        if diffPos == (None, None):
            self.cmd.warn('text=%s' % \
                          (CPL.qstr('SKIPPING large offset (%0.2f,%0.2f) arcsec' % \
                                    (baseDiffPos[0] * 3600.0,
                                     baseDiffPos[1] * 3600.0))))
            diffPos = [0.0, 0.0]
            
        #  - Generate the offset.

        # clip big offsets if we aren't centering up.
        diffSize = math.sqrt(diffPos[0] * diffPos[0] + diffPos[1] * diffPos[1])
        flag = ''
        if doScale and diffSize > (CPL.cfg.get('telescope', 'maxGuideOffset', default=60.0) / (60*60)):
            self.cmd.warn('text=%s' % \
                          (CPL.qstr('SKIPPING huge offset (%0.2f,%0.2f) arcsec' % \
                                    (baseDiffPos[0] * 3600.0,
                                     baseDiffPos[1] * 3600.0))))
            diffPos = [0.0, 0.0]
            
        if diffSize <= (self.tweaks.get('minOffset', 0.1) / (60.0*60.0)):
            self.cmd.warn('text=%s' % \
                          (CPL.qstr('SKIPPING small offset (%0.3f,%0.3f) arcsec' % \
                                    (diffPos[0] * 3600.0,
                                     diffPos[1] * 3600.0))))
            diffPos = [0.0, 0.0]

        self.cmd.respond('measOffset=%0.2f,%0.2f; actOffset=%0.2f,%0.2f' % \
                         (baseDiffPos[0] * 3600, baseDiffPos[1] * 3600,
                          diffPos[0] * 3600, diffPos[1] * 3600))
            

        if diffPos[0] == 0.0 and diffPos[1] == 0.0:
            return '', False

        #  - Threshold computed & uncomputed
        if diffSize > (CPL.cfg.get('telescope', 'maxUncomputedOffset', default=10.0) / (60*60)):
            isUncomputed = False
            flag += "/computed"
        else:
            isUncomputed = True

        cmdTxt = 'offset %s %0.6f,%0.6f %s' % (offsetType, diffPos[0], diffPos[1], flag)
        return cmdTxt, isUncomputed
    
    def _centerUp(self, cmd, star, frame, refGpos, offsetType='guide', doScale=True, fname=''):
        """ Move the given star to/towards the ref pos.

        This is called by the exposure done.  It reads the image, calculates the offsets, and
        updates tcc.  Then, if invalidLoop) is true, call the guideloop again.
        
        Args:
            cmd        - the command that controls us.
            star       - the star that we wwant to move.
            frame      - the GuideFrame star is embedded in.
            refGpos    - the position to move to/towards
            offsetType - 'guide' or 'calibration'
            doScale    - if True, filter the offset according to self.tweaks
        """

        if self.state == 'off':
            return
        if self.state == 'stopping':
            self.stopGuiding()
            return
        if self.invalidLoop:
            # skip this image, something happened
            self._guideLoopTop()
            return

        cmd.warn('debug="state at centerUp: %s"' % self.state)
        cmdTxt, mustWait = self._genOffsetCmd(cmd, star, frame, refGpos,
                                              offsetType, doScale, fname=fname)
        if not cmdTxt:
            self._guideLoopTop()
            return
        if self.cmd.argDict.has_key('noMove'):
            self.cmd.warn('text="NOT sending tcc %s"' % (cmdTxt))
            self._guideLoopTop()
            return
        else:
            # self.cmd.warn('debug=%s' % (CPL.qstr('starting offset: %s' % (cmdTxt))))
            if self.invalidLoop:
                self._guideLoopTop()
                return

            # Arrange for the end of uncomputed offsets to be waited for.
            if mustWait:
                endTime = time.time() + CPL.cfg.get('telescope', 'offsetSettlingTime')
                # set reasonable guess for offset done, and HasMoved will tweak it.
                if endTime > self.offsetWillBeDone:
                    self.offsetWillBeDone = endTime
                self.moving.clear()

            # OK, check one last time before actually moving.
            if self.invalidLoop:
                self._guideLoopTop()
                return
            
            self.genStateKey(action='offsetting')
            cb = client.callback('tcc', cmdTxt, self._doneOffsetting,
                                 cid=self.controller.cidForCmd(self.cmd))

    def _doneOffsetting(self, ret):
        """ Callback called at the end of the guide offset.
        """

        if not ret.ok:
            self.failGuiding('guide offset failed')

        self._guideLoopTop()
        
    def getNextTrackedFilename(self, startName):
        """ If our command requests a filename, we need to read a sequence of files.
        """

        if self.state == 'off':
            return
        if self.state == 'stopping':
            self.stopGuiding()
            return

        if self.trackFilename == None:
            name = self.controller.findFile(self.cmd, self.cmd.qstr(startName))
            if not name:
                raise RuntimeError("no such file: %s" % (startName))
            # self.cmd.warn('debug=%s' % (CPL.qstr("tracking filenames from %s" % (name))))
            self.trackFilename = name
            return name

        filename, ext = os.path.splitext(self.trackFilename)
        basename = filename[:-4]
        idx = int(filename[-4:], 10)
        idx += 1

        newname = "%s%04d%s" % (basename, idx, ext)
        self.trackFilename = newname

        self.cmd.warn('debug=%s' % (CPL.qstr("tracked filename: %s" % (newname))))
        time.sleep(2.0)
        
        return newname

    def _parseISODate(self, dateStr):
        """ Parse a full ISO date.

        Args:
           dateStr   - a string of the form "2005-06-21 01:35:40.198Z" (space might be a 'T')

        Returns:
           - unix seconds
        """

        # change ISO 'T' to space
        parts = dateStr.split('T')
        if len(parts) > 0:
            dateStr = ' '.join(parts)

        # Remove trailing 'Z':
        if dateStr[-1] == 'Z':
            dateStr = dateStr[:-1]
            
        # Peel off fractional seconds
        parts = dateStr.split('.')
        dateStr = parts[0]
        if len(parts) == 1:
            frac = 0.0
        else:
            frac = float(parts[1])
            frac /= 10 ** len(parts[1])

        tlist = time.strptime(dateStr, "%Y-%m-%d %H:%M:%S")
        # self.cmd.warn('debug="exp. middle: %s"' % (tlist))
        secs = time.mktime(tlist)
        return secs + frac
        
    def _getExpMiddle(self, camFile, tweaks):
        """ Return our best estimate of the time of the middle of and exposure.

        Ideally, the camera has a UTMIDDLE card
        Next best is an OBS-DATE card in UTC
        Finally, we just guess.
        
        Args:
            camFile   - a FITS file from a guide camera.

        Returns:
            - unix seconds at the middle of the exposure.
        """

        
        try:
            f = pyfits.open(camFile)
            h = f[0].header
            f.close()
        except Exception, e:
            self.cmd.warn('text=%s' % \
                          (CPL.qstr("Could not open fits file %s: %s" % (camFile, e))))
            h = {}
            
        if h.has_key('UTMIDDLE'):
            t = self._parseISODate(h['UTMIDDLE'])
        elif h.has_key('UTC-OBS') and h.has_key('EXPTIME'):
            t0 = self._parseISODate(h['UTC-OBS'])
            itime = h['EXPTIME']
            t = t0 + (itime / 2.0)
        elif h.has_key('UTTIME') and h.has_key('UTDATE') and h.has_key('EXPTIME'):
            # GimCtrl Echelle slitviewer
            dateStr = "%s %s" % (h['UTDATE'], h['UTTIME'])
            
            tlist = time.strptime(dateStr, "%Y/%m/%d %H:%M:%S")
            t0 = time.mktime(tlist)
            
            itime = h['EXPTIME']
            t = t0 + (itime / 2.0)
        elif h.has_key('DATE-OBS') and h.has_key('TIMESYS') and h.has_key('EXPTIME'):
            t0 = self._parseISODate(h['DATE-OBS'])
            sys = h['TIMESYS']
            itime = h['EXPTIME']

            if sys == 'TAI':
                t0 -= self._startingUTCoffset
            t = t0 + (itime / 2.0)
        else:
            # Total guess. Could keep per-inst readout times, but this'll probably do.
            CPL.log('getExpMiddle', 'guessing, h=%s' % (h))
            t = time.time() - tweaks['exptime'] / 2.0 - 2.0
            
        now = time.time()
        if abs(now - t) > 300:
            self.cmd.warn('text="exposure middle was %d seconds ago; setting to now"' % (now - t))
            t = now
        return t
    
    def _handleGuiderFrame(self, cmd, camFile, frame, tweaks=None, warning=None, failure=None):
        """ Given a new guider frame, calculate and apply the Guide offset and launch
        a new guider frame.
        """

        self.exposing = False

        if warning:
            cmd.warn('text=%s' % (warning))
            
        if failure:
            self.failGuiding('text=%s' % (failure))
            return

        # If we are reading off disk, override camFile, which will be static. 
        # Improve -- CPL
        if self.cmd.argDict.has_key('file'):
            camFile = self.getNextTrackedFilename(self.cmd.argDict['file'])
        elif self.tweaks.has_key('forceFile'):
            camFile = self.getNextTrackedFilename(tweaks['forceFile'])

        # This is a callback, so we need to catch all exceptions.
        try:
            if self.state == 'off':
                return
            if self.state == 'stopping':
                self.stopGuiding()
                return
        
            # Optionally dark-subtract and/or flat-field
            procFile, maskFile, darkFile, flatFile = \
                      self.controller.processCamFile(cmd, camFile, tweaks)
            self.controller.genFilesKey(self.cmd, 'g', True,
                                        procFile, maskFile, camFile, darkFile, flatFile)

            self.genChangedTweaks(self.cmd)
            
            if self.invalidLoop:
                self._guideLoopTop()
                return

            if self.telHasBeenMoved:
                self.genStateKey(action='deferring')
                self.cmd.warn('text=%s' % \
                              (CPL.qstr("guiding deferred: %s" % (self.telHasBeenMoved))))
                self.telHasBeenMoved = False
                self._guideLoopTop()
                return

            # 
            self.genStateKey(action='analysing')
            frame = GuideFrame.ImageFrame(self.controller.size)
            frame.setImageFromFITSFile(procFile)
            self.currentFrame = frame
            
            # A tweak command may have changed the gstar. Incorporate that now.
            # Note that the test should be against None, as an empty list indictates
            # that we should search for good stars.
            if self.newRefStars != None:
                self.cmd.warn('text="changing guide stars"')
                if not self.defineRefStars(self.newRefStars, procFile, frame, tweaks):
                    return
                self.newRefStars = None
                
            # Where should the star have been at the middle of the exposure?
            expMiddle = self._getExpMiddle(procFile, tweaks)
            refPos = None
            try:
                ccdRefPos = self._getExpectedPos(t=expMiddle)
                refPos = frame.ccdXY2imgXY(ccdRefPos)
            except Exception, e:
                if not self.state == 'manual':
                    self.failGuiding(e)
                    return

            # In all cases, find all stars in the field.
            try:
                stars = MyPyGuide.findstars(self.cmd, procFile,
                                            frame, tweaks=self.tweaks)
            except RuntimeError, e:
                stars = []
            except Exception, e:
                CPL.tback('guideloop._handleGuideFrame', e)
                self.failGuiding(e)
                return
            if stars:
                MyPyGuide.genStarKeys(cmd, stars, caller='f')

            # Only try for a centroid if we expect to know where we want to be.
            if self.mode == 'acquire' or \
               self.mode == 'manual' and (self.controller.guiderType == 'gimage' or not refPos):
                star = None
            else:
                self.cmd.respond("guiderPredPos=%0.2f,%0.2f" % (refPos[0], refPos[1]))

                try:
                    star = MyPyGuide.centroid(self.cmd, procFile,
                                              frame, refPos, tweaks=self.tweaks)
                except RuntimeError, e:
                    star = None
                except Exception, e:
                    CPL.tback('guideloop._handleGuideFrame', e)
                    self.failGuiding(e)
                    return

                if star:
                    # We can move the 'c' line into an "else" after TUI 1.2 is the old limit.
                    MyPyGuide.genStarKey(cmd, star, caller='c')

                if self.mode != "manual":
                    MyPyGuide.genStarKey(cmd, star, caller='g', predPos=refPos)

            if self.mode in ('acquire', 'centerUp'):
                self.stopGuiding()
                return
            if self.mode == 'manual':
                delay = self.tweaks.get('manDelay', 0.5)
                if delay > 0.0:
                    self.genStateKey(action='pausing')
                    time.sleep(delay)
                
                self.genStateKey(action='exposing')
                self._guideLoopTop()
                return

            # From here down we care about positions.
            if not frame.imgXYinFrame(refPos):
                CPL.log("GuideLoop",
                        "left frame. ccdRefPos=%0.1f,%0.1f, refPos=%0.1f,%0.1f, frame=%s" % \
                        (ccdRefPos[0], ccdRefPos[1],
                         refPos[0], refPos[1],
                         frame))
                self.failGuiding("guide star moved off frame.")
                return
            
            if not star:
                self.retryGuiding()
                return

            # We have successfully centroided, so reset the number of retries we have made.
            self.retries = 0

            self._centerUp(self.cmd, star, frame, refPos, fname=procFile)
        except Exception, e:
            CPL.tback('guideloop._handleGuideFrame-2', e)
            self.failGuiding(e)
            

