__all__ = ['GuideLoop']

import math
import os
import time

import pyfits

import client
import CPL
import GuideFrame
import MyPyGuide
import Parsing

class GuideLoop(object):
    def __init__(self, controller, cmd, tweaks):
        """ Encapsulate a single guiding loop. 

        Args:
            control   - the controlling object, which we let know when we finish.
            cmd       - the controllng Command.
            tweaks    - a dictionary of variables controlling our behavior.
        """

        self.controller = controller
        self.cmd = cmd
        self.tweaks = tweaks

        self.imCtrName = self.tweaks['imCtrName']
        self.imScaleName = self.tweaks['imScaleName']
        if self.imCtrName[0] == 'G':
            self.frameName = 'gimage'
        else:
            self.frameName = 'inst'
            
        # This controls whether the loop continues or stops, and gives the
        # guider keyword value.
        self.state = 'starting'
        self.action = ''
        
        self.retries = 0
        
        # The 'reference' PVT that we guiding on or to.
        self.refPVT = None
        
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
        
        # What to add to TCC times to get Unix seconds -- get this from the TCC you twit.
        self._startingUTCoffset = -32.0
        self.tccDtime = -3506716800.0 + self._startingUTCoffset

        self.dontCareAboutSlews = False
        
        # We pay attention to a bunch of keywords.
        self.listeners = []
        
        self.loopCnt = 0
        
    def __str__(self):
        return "GuideLoop(guiding=%s, listeners=%s)" % (self.state, self.listeners)
    
    def listenToThem(self):
        self.listeners.append(client.listenFor('tcc', ['MoveItems', 'Moved', 'SlewBeg', 'SlewSuperceded'],
                                               self.listenToMoveItems))
        self.listeners.append(client.listenFor('tcc', ['TCCStatus'], self.listenToTCCStatus))
        self.listeners.append(client.listenFor('tcc', ['Boresight'], self.listenToTCCBoresight))
        self.listeners.append(client.listenFor('tcc', [self.imCtrName], self.listenToTCCImCtr))
        self.listeners.append(client.listenFor('tcc', [self.imScaleName], self.listenToTCCImScale))

            
        self.listeners.append(client.listenFor('tcc', ['SlewEnd'], self.listenToTCCSlewEnd))

        # Force updates of the above keywords:
        client.call("tcc", "show inst/full") # ImCtr, ImScale
        client.call("tcc", "show object") # Boresight
        
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

        The loop sends a copy of the tweaks dictionary down to the exposure and offset callbacks, and
        uses those copies when it runs. But when a new iteration is started, the new tweaks will apply.
        It would be bad to change, say, the binning or windowing between the request for the exposure
        and the calculations of the offset.
        """

        self.tweaks.update(newTweaks)
        self.genTweaksKeys(self.cmd)
        
    def genStateKey(self, cmd=None, state=None, action=None):
        if cmd == None:
            cmd = self.cmd

        if state != None:
            self.state = state
        if action != None:
            self.action = action
        cmd.respond('guideState=%s,%s' % (CPL.qstr(self.state),
                                          CPL.qstr(self.action)))
        
    def cleanup(self):
        """ """

        # TUI generates the slewing ending sound when it sees the "stopping" state.
        # Force that now.
        if self.state != 'stopping':
            self.genStateKey(state='stopping', action='')
            
        self.genStateKey(state='off', action='')
        for i in range(len(self.listeners)):
            CPL.log("GuideLoop.cleanup", "deleting listener %s" % (self.listeners[0]))
            self.listeners[0].stop()
            del self.listeners[0]
        
    def failGuiding(self, why):
        """ Stop guiding, 'cuz something went wrong.
        This must only be called when the loop has stopped.
        """

        self.cleanup()
        self.cmd.fail('text=%s' % (CPL.qstr(why)))
        self.controller.guideLoopIsStopped()

    def stopGuiding(self):
        """ Stop guiding, on purpose
        This must only be called when the loop has stopped.
        """

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
            self._guideLoopTop()
        else:
            self.failGuiding('no star found (after %d retries)' % (self.retries))

    def invalidateLoop(self):
        """ Called when the telescope has moved. """

        self.invalidLoop = True
        
    def restartGuiding(self):
        """ Called when we have moved to a new field.
        """

        self.stopGuiding()

    def isRightPort(self):
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
        
    def run(self):
        """ Actually start the guide loop. """

        rightPort = self.isRightPort()

        if not rightPort:
            return

        self.state = 'starting'
        self.action = ''
        self.genTweaksKeys(self.cmd)
        self.listenToThem()
        
        self._doGuide()
        
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

    def listenToMoveItems(self, reply):
        """ Figure out if the telescope has been moved by examining the TCC's MoveItems key.

        The MoveItems keys always comes with one of:
          - Moved, indicating an immediate offset
              We guestimate the end time, and let the main loop wait on it.
          - SlewBeg, indicating the start of a real slew or a computed offset.
              We
          - SlewSuperceded, dunno exactly how to use that.
          - SlewEnd, indicating the end of a real slew or a computed offset
        """

        if self.dontCareAboutSlews:
            return
        
        mi = reply.KVs.get('MoveItems', 'XXXXXXXX')
        
        # Has an uncomputed offset just been issued?
        if reply.KVs.has_key('Moved'):
            self.invalidateLoop()
            # self.telHasBeenMoved = 'Telescope has been offset'
            endTime = time.time() + CPL.cfg.get('telescope', 'offsetSettlingTime')
            if endTime > self.offsetWillBeDone:
                self.offsetWillBeDone = endTime
            return
        
        # Has a slew/computed offset just been issued? Put this after the MoveItems logic.
        if reply.KVs.has_key('SlewBeg'):
            self.invalidateLoop()
            if mi[1] == 'Y':
                self.cmd.warn('text="Object has been changed. Stopping or restarting guide loop."')
                self.telHasBeenMoved = 'Telescope has been slewed'
                self.restartGuiding()
                return
            else:
                self.cmd.warn('text="Telescope is being slewed; waiting for SlewEnd."')
                self.waitingForSlewEnd = True
            
        if mi[1] == 'Y':
            self.cmd.warn('debug="Object has been changed. Stopping or restarting guide loop."')
            self.restartGuiding()
            return
        if mi[3] == 'Y':
            self.telHasBeenMoved = 'Object offset was changed'
            return
        if mi[4] == 'Y':
            self.telHasBeenMoved = 'Arc offset was changed'
            return
        if mi[5] == 'Y':
            self.telHasBeenMoved = 'Boresight position was changed'
            return
        if mi[6] == 'Y':
            self.telHasBeenMoved = 'Rotation was changed'
            return
        if mi[8] == 'Y':
            self.telHasBeenMoved = 'Calibration offset was changed'
            return
        
    def listenToTCCStatus(self, reply):
        """ Figure out if the telescope has been moved by examining the TCC's TCCStatus key.
        """

        if self.dontCareAboutSlews:
            return
        
        stat = reply.KVs['TCCStatus']
        axisStat = stat[0]

        if 'H' in axisStat:
            self.telHasBeenMoved = 'Telescope is halted'
            self.stop(self.cmd, doFinish=False)
        if 'S' in axisStat:
            self.telHasBeenMoved = 'Telescope was slewed'
    
    def listenToTCCSlewEnd(self, reply):
        """ Wait for a computed offset to finish.
        """

        if self.dontCareAboutSlews:
            return

        if self.waitingForSlewEnd:
            self.waitingForSlewEnd = False
            self.cmd.warn('text="resuming guiding after SlewEnd."')
            self._guideLoopTop()
        
    def listenToTCCBoresight(self, reply):
        """ Figure out if the telescope has been moved by examining the TCC's TCCStatus key.
        """
        
        k = reply.KVs['Boresight']
        pvt = list(map(float, k))
        self.boresightOffset = pvt
        self.cmd.warn('debug="set boresight offset to (%s)"' % \
                      (self.boresightOffset))
    
    def listenToTCCImCtr(self, reply):
        """ Set the guider/instrument center pixel.
        """

        k = reply.KVs[self.imCtrName]
        self.boresight = map(float, k)
        self.cmd.warn('debug="set boresight pos to (%0.2f, %0.2f)"' % \
                      (self.boresight[0], self.boresight[1]))
        
    def listenToTCCImScale(self, reply):
        """ Set the guider/instrument scales.
        """

        k = reply.KVs[self.imScaleName]
        self.imScale = map(float, k)
        self.cmd.warn('debug="set imscale to (%0.2f, %0.2f)"' % \
                      (self.imScale[0], self.imScale[1]))
        
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
            
            ctr = self.boresight
            self.tweaks['window'] = (ctr[0]-size[0], ctr[1]-size[1],
                                     ctr[0]+size[0], ctr[1]+size[1])
        
    def _doGuide(self):
        """ Actually start guiding.

        Examines parts of the .tweaks dictionary for several things:
           time     - seconds to expose

           guideStar=X,Y   - the position to start centroiding on.
        or:
           centerFrom=X,Y  - the position of a star to move to the boresight.

        If neither is specified, run a findstars and guide on the "best" return.
        """

        CPL.log("_doGuide", "tweaks=%s" % (self.tweaks))
        
        # Steps:
        #  1) Look for at-start offsets (centerOn=X,Y or gstar=X,Y
        #      if specified, use specified position to seed centroid()
        #      then move the result to the boresight.
        #
        centerOn = self.cmd.argDict.get('centerOn')
        gstar = self.cmd.argDict.get('gstar')
        boresight = self.cmd.argDict.get('boresight', 'nope')
        boresight = boresight != 'nope'
        manual = self.cmd.argDict.get('manual', 'nope')
        manual = manual != 'nope'
        
        if (boresight or centerOn) and gstar:
            self.failGuiding('cannot specify both field and boresight guiding.')
            return

        if manual:
            if boresight or centerOn or gstar:
                self.failGuiding('cannot specify both manual and automatic guiding.')
                return
            
            self.checkSubframe()

            self.guidingType = 'manual'
            self.genStateKey(state='starting')
            self.state = 'on'
            self.controller.doCmdExpose(self.cmd, self._handleGuiderFrame,
                                        'expose', tweaks=self.tweaks)
            return
            
        if boresight:
            # Simply start nudging the object nearest the boresight to the boresight
            #
            self.guidingType = 'boresight'
            self.refPVT = None

            self.checkSubframe()
            
            self.genStateKey(state='starting')
            self.state = 'on'
            self.controller.doCmdExpose(self.cmd, self._handleGuiderFrame,
                                        'expose', tweaks=self.tweaks)
            return
        
        if centerOn:
            # if "centerOn" is specified, offset the given position to the boresight,
            # then continue nudging it there.
            #
            try:
                seedPos = self.controller.parseCoord(centerOn)
            except Exception, e:
                self.failGuiding('could not parse the centerOn position: %s.' % (e))
                return

            self.guidingType = 'boresight'
            self.tweaks['centerOn'] = seedPos

            if self.cmd.argDict.has_key('noGuide'):
                self.tweaks['noGuide'] = True
                self.dontCareAboutSlews = True
                self.centerAndExpose(self.cmd)
                return
            
        elif gstar:
            # if "gstar" is specified, use that as the guide star.
            #
            try:
                seedPos = self.controller.parseCoord(gstar)
            except Exception, e:
                CPL.tback('guideloop._doGuide', e)
                self.failGuiding(e)
                return
                
            self.guidingType = 'field'
            self.tweaks['gstars'] = [seedPos]
            
        else:
            # otherwise use the "best" object as the guide star.
            #
            self.guidingType = 'field'

        if not self.tweaks.has_key('noGuide'):
            self.genStateKey(state='starting')
        self.controller.doCmdExpose(self.cmd, self._firstExposure, 'expose', self.tweaks)

    def centerUp(self, cmd, tweaks):

        # if "centerOn" is specified, offset the given position to the boresight,
        # then continue nudging it there.
        seedPos = tweaks['centerOn']

        self.cmd.respond('text="offsetting object at (%0.1f, %0.1f) to the boresight...."' % \
                         (seedPos[0], seedPos[1]))
        try:
            refpos = self.getBoresight()
            frame = GuideFrame.ImageFrame(self.controller.size)
            CCDstar = MyPyGuide.imgPos2CCDXY(seedPos, frame)
            cmdTxt, mustWait = self._genOffsetCmd(cmd, CCDstar,
                                                  frame, refpos,
                                                  offsetType='guide',
                                                  doScale=False)
            self.genStateKey(action='centering')
            ret = client.call('tcc', cmdTxt,
                        cid=self.controller.cidForCmd(self.cmd))
                
        except Exception, e:
            CPL.tback('centerUp.1', e)
            cmd.fail('text=%s' % (CPL.qstr(e)))
            return
        
        if not ret.ok:
            cmd.fail('text="centering offset failed"')
        else:
            cmd.finish()
            
            
    def centerAndExpose(self, cmd):

        # if "centerOn" is specified, offset the given position to the boresight,
        # then continue nudging it there.
        seedPos = self.tweaks['centerOn']

        self.cmd.respond('text="offsetting object at (%0.1f, %0.1f) to the boresight...."' % \
                         (seedPos[0], seedPos[1]))
        try:
            refpos = self.getBoresight()
            frame = GuideFrame.ImageFrame(self.controller.size)
            CCDstar = MyPyGuide.imgPos2CCDXY(seedPos, frame)
            cmdTxt, mustWait = self._genOffsetCmd(cmd, CCDstar,
                                                  frame, refpos,
                                                  offsetType='guide',
                                                  doScale=False)
            self.genStateKey(action='offsetting')
            ret = client.call('tcc', cmdTxt,
                        cid=self.controller.cidForCmd(self.cmd))
            if mustWait:
                time.sleep(CPL.cfg.get('telescope', 'offsetSettlingTime'))
            self.genStateKey(action='exposing')
            self.controller.doCmdExpose(self.cmd, self._handleGuiderFrame,
                                        'expose', tweaks=self.tweaks)

        except Exception, e:
            CPL.tback('guideloop._firstExposure-2', e)
            self.failGuiding(e)
            return

        if not ret.ok:
            self.failGuiding('centering offset failed')
            return
            
    def _firstExposure(self, cmd, camFile, frame, tweaks=None, warning=None, failure=None):
        """ Callback called when the first guide loop exposure is available.

        Handles the following issues:
          - if 'centerOn' is specified, move that to the boresight, then start boresight guiding.
          - if a 'gstar' is specified, mark that as the guide star.
          - otherwise find the best star in the field and guide on that.
          
        Args:
             cmd        - same as self.cmd, and ignored.
             camFile   - an absolute pathname for the guider image.
             frame      - a GuideFrame describing the image.
             tweaks     - same as self.tweaks, and ignored.
        """

        if warning:
            cmd.warn('text=%s' % (warning))
            
        if failure:
            self.failGuiding('text=%s' % (failure))
            return

        if self.state == 'off':
            return
        if self.state == 'stopping':
            self.stopGuiding()
            return
        if self.invalidLoop:
            self._guideLoopTop()
            return
        
        
        # Optionally dark-subtract and/or flat-field
        procFile, maskFile, darkFile, flatFile = \
                  self.controller.processCamFile(cmd, camFile, self.tweaks)

        if self.tweaks.has_key('centerOn'):
            
            # if "centerOn" is specified, offset the given position to the boresight,
            # then continue nudging it there.
            seedPos = self.tweaks['centerOn']
            self.cmd.respond('text="offsetting object at (%0.1f, %0.1f) to the boresight...."' % \
                             (seedPos[0], seedPos[1]))
            try:
                refpos = self.getBoresight()
                CCDstar = MyPyGuide.imgPos2CCDXY(seedPos, frame)
                cmdTxt, mustWait = self._genOffsetCmd(cmd, CCDstar, frame, refpos, offsetType='guide', doScale=False)
                if self.cmd.argDict.has_key('noMove'):
                    self.cmd.warn('text="NOT sending tcc %s"' % (cmdTxt))
                # If we just want to center up and confirm the star, shortcut here
                elif self.tweaks.has_key('noGuide'):
                    client.call('tcc', cmdTxt,
                                 cid=self.controller.cidForCmd(self.cmd))
                    self.stopGuiding()
                    #self.state = 'offsetting'
                    #self.controller.doCmdExpose(self.cmd, self._handleGuiderFrame,
                    #                            'expose', tweaks=self.tweaks)
                    return
                else:
                    if self.invalidLoop:
                        self._guideLoopTop()
                        return
                    if mustWait:
                        endTime = time.time() + CPL.cfg.get('telescope', 'offsetSettlingTime')
                        if endTime > self.offsetWillBeDone:
                            self.offsetWillBeDone = endTime
                    ret = client.call('tcc', cmdTxt, cid=self.controller.cidForCmd(self.cmd))
            except Exception, e:
                CPL.tback('guideloop._firstExposure-2', e)
                self.failGuiding(e)
                return

            if not ret.ok:
                self.failGuiding('centering offset failed')
                return
            
            # If we just want to center up and confirm the star, shortcut here
            if self.tweaks.has_key('noGuide'):
                self._guideLoopTop()
                return
            
        elif self.tweaks.has_key('gstars'):
            # if "gstar" is specified, use that as the guide star.
            #

            seeds = self.tweaks['gstars']
            seedPos = seeds[0]
            try:
                star = MyPyGuide.centroid(self.cmd, camFile, maskFile,
                                          frame, seedPos, self.tweaks)
                if not star:
                    self.failGuiding('no star found near (%0.1f, %0.1f)' % (seedPos[0], seedPos[1]))
                    return
            except Exception, e:
                CPL.tback('guideloop._firstExposure-3', e)
                self.failGuiding(e)
                return

            try:
                CCDstar = MyPyGuide.star2CCDXY(star, frame)
                self.refPVT = self._Frame2ICRS(CCDstar.ctr)

                # Per Russell: make sure to zero out the velocities on the ICRS reference
                # position.
                #
                self.refPVT[1] = self.refPVT[4] = 0.0
                
            except Exception, e:
                self.failGuiding('could not establish the guidestar coordinates: %s' % (e))
                return
        else:
            # otherwise use the "best" object as the guide star.
            #
            try:
                stars = MyPyGuide.findstars(self.cmd, camFile, maskFile,
                                            frame, self.tweaks)
                if not stars:
                    self.failGuiding("no stars found")
                    return

                CCDstar = MyPyGuide.star2CCDXY(stars[0], frame)
                self.refPVT = self._Frame2ICRS(CCDstar.ctr)

                # Per Russell: make sure to zero out the velocities on the ICRS reference
                # position.
                #
                self.refPVT[1] = self.refPVT[4] = 0.0
            except Exception, e:
                self.failGuiding('could not establish guide star coordinates: %s' % (e))
                return

        #  4) start the guiding loop:
        #
        self.genStateKey(state='on')
        self._guideLoopTop()

    def _guideLoopTop(self):
        """ The "top" of the guiding loop.

        This is
           a) one place where the loop gets stopped and
           b) where the loop gets deferred should an immediate move (an uncomputed offset)
           have been started,

        """

        self.invalidLoop = False
        
        if self.state == 'off':
            return
        if self.state == 'stopping':
            self.stopGuiding()
            return

        if self.waitingForSlewEnd:
            self.genStateKey(action='deferring')
            self.cmd.warn('text="waiting for offset to finish"')
            return
        
        if self.offsetWillBeDone > 0.0:
            self.genStateKey(action='deferring')
            diff = self.offsetWillBeDone - time.time()

            if diff > 0.0:
                CPL.log('gcam',
                        'deferring guider frame for %0.2f seconds to allow immediate offset to finish' % (diff))
                time.sleep(diff)        # Yup. Better be short, hunh?
            self.offsetWillBeDone = 0.0

        self.genStateKey(action='exposing')
        self.controller.doCmdExpose(self.cmd, self._handleGuiderFrame,
                                    'expose', tweaks=self.tweaks)
        
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

        # Guage star quality somehow.


        # Convert to axis arcsec
        fitErrors = (abs(star.err[0] * 3600.0 / self.imScale[0]),
                     abs(star.err[1] * 3600.0 / self.imScale[1]))

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
        """ Return the next (toy, test) trailing offset, in degrees. """

        if not self.doTrail:
            return [0.0, 0.0]
        
        # Move .trailingStep each offset we take. When we reach the end (.trailingLimit),
        # turn around.
        #
        if abs(self.trailingOffset) >= self.trailingLimit:
            self.trailingDir *= -1
            
        self.trailingOffset += self.trailingDir * self.trailingStep

        return [0.0, self.trailingOffset]

    def TAI2UTC(self, tai):
        return tai + self.tccDtime

    def UTC2TAI(self, utc):
        return utc - self.tccDtime
    
    def PVT2pos(self, pvt, t=None):
        """ Evaluate a PVT to the given time (or to now).

        Args:
             pvt     - a TCC coord2 (p,v,t,p2,v2,t2)
             t       - a UTC time. If None, use "now".

        Returns:
             (x, y)
        """

        CPL.log('PVT2pos', CPL.qstr("PVT2pos(utc=%s, pvt=%s)" % (t, pvt)))

        if not t:
            t = time.time()
        t = self.UTC2TAI(t)

        CPL.log('PVT2pos', CPL.qstr("PVT2pos(tai=%s, pvt=%s)" % (t, pvt)))

        td = t - pvt[2]
        x = pvt[0] + pvt[1] * td
        
        td = t - pvt[5]
        y = pvt[3] + pvt[4] * td

        CPL.log('PVT2pos', CPL.qstr("td=%0.4f; x=%0.4f; y=%0.4f)" % (td, x, y)))

        return x, y

    def getBoresight(self, t=None):
        """ Figure out the boresight position for a given time.

        The effective boresight is the sum of the instrument/guider center and the
        boresight offset. 

        Args:
             t       ? time, in Unix seconds, to reckon the boresight at.

        Returns:
            - the boresight position at t, as an x,y pair of pixel
        """

        if t == None:
            t = time.time()

        # Evaluate the boresight offset for t. In degrees.
        bsPos = self.PVT2pos(self.boresightOffset, t)

        # Add the offset to the ImCtr boresight pixel.
        xPos = self.boresight[0] + self.imScale[0] * bsPos[0]
        yPos = self.boresight[1] + self.imScale[1] * bsPos[1]

        # self.cmd.warn('debug="boresight is at (%0.2f, %0.2f)"' % (xPos, yPos))
        return xPos, yPos

    def _getExpectedPos(self, t=None):
        """ Return the expected position of the guide star in GPos coordinates. """

        if self.guidingType == 'field':
            pvt = self._ICRS2Frame(self.PVT2pos(self.refPVT, t=t))
            return self.PVT2pos(pvt, t=t)
        else:
            return self.getBoresight(t)

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

        # We know the boresight pixel .boresightPixel and the source pixel fromPixel.
        #  - Convert each to Observed positions
        #
        now = time.time()
        refPVT = self._Frame2Obs(refGpos)
        starPVT = self._Frame2Obs(star.ctr)
        
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

        refPos = self.PVT2pos(refPVT, t=now)
        starPos = self.PVT2pos(starPVT, t=now)
        baseDiffPos = [starPos[0] - refPos[0], \
                       starPos[1] - refPos[1]]

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
            
        #  - Generate the offset. Threshold computed & uncomputed
        #
        diffSize = math.sqrt(diffPos[0] * diffPos[0] + diffPos[1] * diffPos[1])
        flag = ''
        if diffSize > (CPL.cfg.get('telescope', 'maxUncomputedOffset', default=10.0) / (60*60)):
            isUncomputed = False
            flag += "/computed"
        else:
            isUncomputed = True

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

        cmdTxt = 'offset %s %0.6f,%0.6f %s' % (offsetType, diffPos[0], diffPos[1], flag)
        return cmdTxt, isUncomputed
    
    def _centerUp(self, cmd, star, frame, refGpos, offsetType='guide', doScale=True, fname=''):
        """ Move the given star to/towards the ref pos.
        
        Args:
            cmd        - the command that controls us.
            star       - the star that we wwant to move.
            frame      - the GuideFrame star is embedded in.
            refGpos    - the position to move to/towards
            offsetType - 'guide' or 'calibration'
            doScale    - if True, filter the offset according to self.tweaks
        """

        # self.controller.xxxCmd(cmd, '_centerUp')

        if self.state == 'off':
            return
        if self.state == 'stopping':
            self.stopGuiding()
            return
        if self.invalidLoop:
            self._guideLoopTop()
            return

        cmdTxt, mustWait = self._genOffsetCmd(cmd, star, frame, refGpos, offsetType, doScale, fname=fname)
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
                if endTime > self.offsetWillBeDone:
                    self.offsetWillBeDone = endTime

            self.genStateKey(action='offsetting')
            cb = client.callback('tcc', cmdTxt, self._doneOffsetting,
                                 cid=self.controller.cidForCmd(self.cmd))

        # self.controller.xxxCmd(cmd, '_centerUp_end')

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
            self.cmd.warn('debug=%s' % (CPL.qstr("tracking filenames from %s" % (name))))
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
        self.cmd.warn('debug="exp. middle: %s"' % (tlist))
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
        elif h.has_key('UTC-OBS'):
            t0 = self._parseISODate(h['UTC-OBS'])
            itime = h['EXPTIME']
            t = t0 + (itime / 2.0)
        elif h.has_key('UTTIME') and h.has_key('UTDATE'):
            # GimCtrl Echelle slitviewer
            dateStr = "%s %s" % (h['UTDATE'], h['UTTIME'])
            
            tlist = time.strptime(dateStr, "%Y/%m/%d %H:%M:%S")
            t0 = time.mktime(tlist)
            
            itime = h['EXPTIME']
            t = t0 + (itime / 2.0)
        elif h.has_key('DATE-OBS'):
            t0 = self._parseISODate(h['DATE-OBS'])
            sys = h['TIMESYS']
            itime = h['EXPTIME']

            if sys == 'TAI':
                t0 -= self._startingUTCoffset
            t = t0 + (itime / 2.0)
        else:
            # Total guess. Could keep per-inst readout times, but this'll probably do.
            t = time.time() - tweaks['exptime'] / 2.0 - 2.0

        now = time.time()
        if abs(now - t) > 100:
            self.cmd.warn("exposure middle was %d seconds from now" % (t - now))
        return t
    
    def _handleGuiderFrame(self, cmd, camFile, frame, tweaks=None, warning=None, failure=None):
        """ Given a new guider frame, calculate and apply the Guide offset and launch
        a new guider frame.
        """

        if warning:
            cmd.warn('text=%s' % (warning))
            
        if failure:
            self.failGuiding('text=%s' % (failure))
            return

        # self.controller.xxxCmd(cmd, '_handleGuiderFrame')
        
        # This is a callback, so we need to catch all exceptions.
        try:
            if self.state == 'off':
                return
            if self.state == 'stopping':
                self.stopGuiding()
                return
            if self.invalidLoop:
                self._guideLoopTop()
                return

            #self.cmd.warn('debug=%s' % (CPL.qstr('new guide camera file=%s, frame=%s' % \
            #                                     (camFile, frame))))

            if self.telHasBeenMoved:
                self.genStateKey(action='deferring')
                self.cmd.warn('text=%s' % \
                              (CPL.qstr("guiding deferred: %s" % (self.telHasBeenMoved))))
                self.telHasBeenMoved = False
                self._guideLoopTop()
                return

            if self.cmd.argDict.has_key('file'):
                camFile = self.getNextTrackedFilename(self.cmd.argDict['file'])
            elif self.tweaks.has_key('forceFile'):
                camFile = self.getNextTrackedFilename(self.tweaks['forceFile'])

            # Optionally dark-subtract and/or flat-field
            procFile, maskFile, darkFile, flatFile = \
                      self.controller.processCamFile(cmd, camFile, self.tweaks)
            # self.controller.xxxCmd(cmd, '_handleGuiderFrame_2')

            self.controller.genFilesKey(self.cmd, 'g', True,
                                        procFile, maskFile, camFile, darkFile, flatFile)
            self.genChangedTweaks(self.cmd)
            
            if self.tweaks.has_key('noGuide'):
                self.stopGuiding()
                return
            
            self.genStateKey(action='analysing')
            frame = GuideFrame.ImageFrame(self.controller.size)
            frame.setImageFromFITSFile(procFile)

            if self.guidingType == 'manual':
                expMiddle = self._getExpMiddle(camFile, tweaks)
                now = time.time()
                cmd.warn('debug="exposure middle was %0.1f sec ago."' % (now - expMiddle))
                try:
                    stars = MyPyGuide.findstars(self.cmd, procFile, maskFile,
                                            frame, tweaks=self.tweaks)
                except RuntimeError, e:
                    stars = []

                if stars:
                    MyPyGuide.genStarKeys(cmd, stars, caller='f')

                delay = self.tweaks.get('manDelay', 0.0)
                if delay > 0.0:
                    self.genStateKey(action='pausing')
                    time.sleep(delay)
                
                self.genStateKey(action='exposing')
                self.controller.doCmdExpose(self.cmd, self._handleGuiderFrame,
                                            'expose', tweaks=self.tweaks)
                return
                
            # Where should the star have been at the middle of the exposure?
            expMiddle = self._getExpMiddle(camFile, tweaks)
            ccdRefPos = self._getExpectedPos(t=expMiddle)
            refPos = frame.ccdXY2imgXY(ccdRefPos)
            self.cmd.respond("guiderPredPos=%0.2f,%0.2f" % (refPos[0], refPos[1]))

            if not frame.imgXYinFrame(refPos):
                CPL.log("GuideLoop", "left frame. ccdRefPos=%0.1f,%0.1f, refPos=%0.1f,%0.1f, frame=%s" % \
                        (ccdRefPos[0], ccdRefPos[1],
                         refPos[0], refPos[1],
                         frame))
                self.failGuiding("guide star moved off frame.")
                return
            
            # self.controller.xxxCmd(cmd, '_handleGuiderFrame_3')
            try:
                star = MyPyGuide.centroid(self.cmd, procFile, maskFile,
                                          frame, refPos, tweaks=self.tweaks)
                if not star:
                    raise RuntimeError('no star found')
            except RuntimeError, e:
                self.retryGuiding()
                return
            except Exception, e:
                CPL.tback('guideloop._handleGuideFrame', e)
                self.failGuiding(e)
                return

            # We have successfully centroided, so reset the number of retries we have made.
            self.retries = 0

            # self.controller.xxxCmd(cmd, '_handleGuiderFrame_4')
            # Get the other stars in the field
            try:
                stars = MyPyGuide.findstars(self.cmd, procFile, maskFile,
                                            frame, tweaks=self.tweaks)
            except RuntimeError, e:
                stars = []

            MyPyGuide.genStarKey(cmd, star, caller='c')
            if stars:
                MyPyGuide.genStarKeys(cmd, stars, caller='f')

            if self.tweaks.has_key('noGuide'):
                self.stopGuiding()
            else:
                self._centerUp(self.cmd, star, frame, refPos, fname=procFile)
        except Exception, e:
            CPL.tback('guideloop._handleGuideFrame-2', e)
            self.failGuiding(e)
            
        # self.controller.xxxCmd(cmd, '_handleGuiderFrame_end')

    def _extractCnvPos(self, res):
        """ Extract and convert the converted position from a tcc convert.

        Returns:
           P,V,T, P2,V2,T2
        """

        def floatOrRaise(s):
            """ Convert a floating point number, but raise an exception if the number is 'nan' """

            s = s.lower()
            if s == 'nan':
                raise ValueError('NaN is not acceptable here.')

            return float(s)
        
        cvtPos = res.KVs.get('ConvPos', None)

        if not res.ok or cvtPos == None:
            CPL.log('GuideLoop', 'no coordinate conversion (ok=%s)' % (res.ok))
            raise RuntimeError('not tracking the sky')
        else:
            try:
                cvtPos = map(floatOrRaise, cvtPos)
            except Exception, e:
                CPL.log('GuideLoop', 'no coordinate conversion (ok=%s)' % (res.ok))
                raise RuntimeError('not tracking the sky')

        return cvtPos

    def _checkCoordinates(self, pos):
        """ Check whether pos is a valid pair of valid coordinates. """

        if "%s" % pos[0] == 'nan' or "%s" % pos[1] == 'nan':
            self.failGuiding('cannot convert undefined coordinates')
            
    def _pixels2inst(self, pos):
        # (pos - centPix) / pix/deg

        instPos = ((pos[0] - self.boresight[0]) / self.imScale[0], \
                   (pos[1] - self.boresight[1]) / self.imScale[1])

        return instPos
    
    def _inst2pixels(self, pos):
        # (pos * pix/deg) + ctrPix

        pixel = ((pos[0] * self.imScale[0]) + self.boresight[0],
                 (pos[1] * self.imScale[1]) + self.boresight[1])

        return pixel
    
    def _Frame2ICRS(self, pos):
        """ Convert a Guide frame coordinate to an ICRS coordinate. """        

        if self.frameName == 'inst':
            pos = self._pixels2inst(pos)
            
        # self.cmd.respond('debug=%s' % (CPL.qstr("gpos2ICRS pos=%r" % (pos,))))

        self._checkCoordinates(pos)
        ret = client.call("tcc", "convert %0.5f,%0.5f %s icrs" % (pos[0], pos[1], self.frameName),
                          cid=self.controller.cidForCmd(self.cmd))
        return self._extractCnvPos(ret)
    
    def _Frame2Obs(self, pos):
        """ Convert a Guide frame coordinate pair to an Observed coordinate pair.

        Args:
            pos   - pos1,pos2

        Returns:
            cvtpos1, cvtpos2
        """

        if self.frameName == 'inst':
            pos = self._pixels2inst(pos)
            
        # self.cmd.respond('debug=%s' % (CPL.qstr("gpos2Obs pos=%r" % (pos,))))        
        self._checkCoordinates(pos)

        ret = client.call("tcc", "convert %0.5f,%0.5f %s obs" % (pos[0], pos[1], self.frameName),
                          cid=self.controller.cidForCmd(self.cmd))
        return self._extractCnvPos(ret)
    
    def _ICRS2Obs(self, pos):
        """ Convert an ICRS coordinate to an Observed coordinate. """

        # self.cmd.respond('debug=%s' % (CPL.qstr("ICRS2Obs pos=%r" % (pos,))))        
        self._checkCoordinates(pos)

        ret = client.call("tcc", "convert %0.5f,%0.5f icrs obs" % (pos[0], pos[1]),
                          cid=self.controller.cidForCmd(self.cmd))
        return self._extractCnvPos(ret)

    def _ICRS2Frame(self, pos):
        """ Convert an ICRS coordinate to a guider frame coordinate. """

        # self.cmd.respond('debug=%s' % (CPL.qstr("ICRS2Frame pos=%r" % (pos,))))        
        self._checkCoordinates(pos)

        ret = client.call("tcc", "convert %0.5f,%0.5f icrs %s" % (pos[0], pos[1], self.frameName),
                          cid=self.controller.cidForCmd(self.cmd))
        pos = self._extractCnvPos(ret)
    
        if self.frameName == 'inst':
            pos = self._inst2pixels(pos)

        return pos
