__all__ = ['GuideLoop']

import math
import os
import time

import client
import CPL
import GuideFrame
import MyPyGuide

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

        # This controls wwhether the loop continues or stops.
        self.guiding = False
        self.refpos = None
        
        # If we are "guiding" on a file sequence, track the sequence here.
        self.trackFilename = None
        
        self._initTrailing()

        # We listen for changes in TCC keywords that indicate that a guider frame
        # may not be valid, and guess when an uncomputed offset will be done.
        #
        self.telHasBeenMoved = False
        self.offsetWillBeDone = 0.0

        # What to add to TCC times to get Unix seconds
        self._startingUTCoffset = -32.0
        self.tccDtime = -3506716800.0 + self._startingUTCoffset

        self.listeners = []
        self.listeners.append(client.listenFor('tcc', ['MoveItems', 'Moved'], self.listenToMoveItems))
        self.listeners.append(client.listenFor('tcc', ['TCCStatus'], self.listenToTCCStatus))
        self.listeners.append(client.listenFor('tcc', ['Boresight'], self.listenToTCCBoresight))
        self.listeners.append(client.listenFor('tcc', ['GImCtr'], self.listenToTCCImCtr))
        self.listeners.append(client.listenFor('tcc', ['GImScale'], self.listenToTCCImScale))

        # Force a couple of updates:
        client.call("tcc", "show inst/full") # ImCtr, ImScale
        client.call("tcc", "show object") # Boresight
        
    def __str__(self):
        return "GuideLoop(guiding=%s, listeners=%s)" % (self.guiding, self.listeners)
    
    def cleanup(self):
        """ """
        
        self.guiding = False
        for i in range(len(self.listeners)):
            CPL.log("GuideLoop.cleanup", "deleting listener %s" % (self.listeners[0]))
            self.listeners[0].stop()
            del self.listeners[0]
        
    def failGuiding(self, why):
        """ Stop guiding, 'cuz something went wrong.
        This must only be called when the loop has stopped.
        """

        self.cleanup()

        self.cmd.respond('guiding=%s' % CPL.qstr(self.guiding))
        self.cmd.fail('%sTxt=%s' % (self.controller.name, CPL.qstr(why)))
        self.controller.guideLoopIsStopped()

    def stopGuiding(self):
        """ Stop guiding, on purpose
        This must only be called when the loop has stopped.
        """

        self.cleanup()
        
        self.cmd.finish('guiding=%s' % CPL.qstr(self.guiding))
        self.controller.guideLoopIsStopped()
        
    def run(self):
        """ Actually start the guide loop. """

        self.guiding = True
        self._doGuide()
        
    def stop(self, cmd, doFinish=True):
        """ A way for the outside world to stop the loop.

        This merely sets a flag that other parts of the loop examine at appropriate times.
        """

        if doFinish:
            cmd.finish('%sTxt="stopping guide loop...."' % (self.controller.name))
        else:
            cmd.respond('%sTxt="stopping guide loop...."' % (self.controller.name))
        self.guiding = False
        
    def listenToMoveItems(self, reply):
        """ Figure out if the telescope has been moved by examining the TCC's MoveItems key.
        """

        # Has an uncomputed offset just been issued?
        if reply.KVs.has_key('Moved'):
            self.telHasBeenMoved = 'Telescope has been offset'
            self.offsetWillBeDone = time.time() + CPL.cfg.get('telescope', 'offsetSettlingTime')
            return
        
        mi = reply.KVs['MoveItems']
        if mi[1] == 'Y':
            self.telHasBeenMoved = 'Object was changed'
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
            self.telHasBeenMoved = 'Rotator was moved'
            return
        if mi[8] == 'Y':
            self.telHasBeenMoved = 'Calibration offset was changed'
            return
        
    def listenToTCCStatus(self, reply):
        """ Figure out if the telescope has been moved by examining the TCC's TCCStatus key.
        """

        stat = reply.KVs['TCCStatus']
        axisStat = stat[0]

        if 'H' in axisStat:
            self.telHasBeenMoved = 'Telescope has been halted'
            self.stop(self.cmd, doFinish=False)
        if 'S' in axisStat:
            self.telHasBeenMoved = 'Telescope was slewed'
    
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

        k = reply.KVs['GImCtr']
        self.boresight = map(float, k)
        self.cmd.warn('debug="set boresight pos to (%0.2f, %0.2f)"' % \
                      (self.boresight[0], self.boresight[1]))
        
    def listenToTCCImScale(self, reply):
        """ Set the guider/instrument scales.
        """

        k = reply.KVs['GImScale']
        self.imScale = map(float, k)
        self.cmd.warn('debug="set imscale to (%0.2f, %0.2f)"' % \
                      (self.imScale[0], self.imScale[1]))
        
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
        
        self.guiding = True
        self.controller.doCmdExpose(self.cmd, self._firstExposure, 'expose', self.tweaks)

    def _firstExposure(self, cmd, filename, frame, tweaks=None):
        """ Callback called when the first guide loop exposure is available.

        Handles the following issues:
          - if 'centerOn' is specified, move that to the boresight, then start boresight guiding.
          - if a 'gstar' is specified, mark that as the guide star.
          - otherwise find the 
          
        Args:
             cmd        - same as self.cmd, and ignored.
             filename   - an absolute pathname for the guider image.
             frame      - a GuideFrame describing the image.
             tweaks     - same as self.tweaks, and ignored.
        """

        if not self.guiding:
            self.stopGuiding()
            return
        
        # Steps:
        #  1) Look for at-start offsets (centerOn=X,Y or gstar=X,Y
        #      if specified, use specified position to seed centroid()
        #      then move the result to the boresight.
        #
        centerOn = self.cmd.argDict.get('centerOn')
        gstar = self.cmd.argDict.get('gstar')
        boresight = self.cmd.argDict.get('boresight', 'nope')
        boresight = boresight != 'nope'
        
        if (boresight or centerOn) and gstar:
            self.failGuiding('cannot specify both field and boresight guiding.')
            return

        if boresight:
            # Simply start nudging the object nearest the boresight to the boresight
            #
            self.guidingType = 'boresight'
            try:
                self.refPVT = self._GPos2ICRS(self.getBoresight())
            except Exception, e:
                self.failGuiding('could not establish the boresight: %s.' % (e))
                return
                
        elif centerOn:
            # if "centerOn" is specified, offset the given position to the boresight,
            # then continue nudging it there.
            #
            self.guidingType = 'boresight'
            try:
                seedPos = self.controller.parseCoord(centerOn)
            except Exception, e:
                self.failGuiding('could not parse the centerOn position: %s.' % (e))
                return

            #seedPos = frame.ccdXY2imgXY(seedPos)
            self.cmd.respond('txt="offsetting object at (%d, %d) to the boresight...."' % \
                             (seedPos[0], seedPos[1]))
            try:
                star = MyPyGuide.centroid(self.cmd, filename, self.controller.mask,
                                          frame, seedPos, self.tweaks)
                if not star:
                    raise RuntimeError('no star found near (%d, %d)' % seedPos)
            except RuntimeError, e:
                self.failGuiding(e)
                return

            try:
                self.refPVT = self._GPos2ICRS(self.getBoresight())
                offsetCmd = self._genOffsetCmd(cmd, star, frame, offsetType='calib', doScale=False)
                if self.cmd.argDict.has_key('noMove'):
                    self.cmd.warn('%sTxt="NOT sending tcc %s"' % (self.controller.name, cmdTxt))
                else:
                    client.call('tcc', cmdTxt, cid=self.controller.cidForCmd(self.cmd))
            except Exception, e:
                self.failGuiding(e)
                return
            
        elif gstar:
            # if "gstar" is specified, use that as the guide star.
            #
            try:
                seedPos = self.controller.parseCoord(gstar)
            except Exception, e:
                self.failGuiding(e)
                return
                
            try:
                star = MyPyGuide.centroid(self.cmd, filename, self.controller.mask,
                                          frame, seedPos, self.tweaks)
                if not star:
                    raise RuntimeError('no star found near (%d, %d)' % seedPos)
            except RuntimeError, e:
                self.failGuiding(e)
                return

            self.guidingType = 'field'

            try:
                self.refPVT = self._GPos2ICRS(star.ctr)
            except Exception, e:
                self.failGuiding('could not establish the star coordinates: %s' % (e))

        else:
            # otherwise use the "best" object as the guide star.
            #
            try:
                isSat, stars = MyPyGuide.findstars(self.cmd, filename, self.controller.mask,
                                                   frame, self.tweaks)
                if not stars:
                    self.failGuiding("no stars found")
                    return

                startPos = stars[0].ctr
                self.guidingType = 'field'
                self.refPVT = self._GPos2ICRS(startPos)
            except Exception, e:
                self.failGuiding('could not establish guide star coordinates: %s' % (e))
                return

        #  4) start the guiding loop:
        #
        self.cmd.respond('guiding=True')
        self._guideLoopTop()
        
    def _guideLoopTop(self):
        """ The "top" of the guiding loop.

        This is
           a) one place where the loop gets stopped and
           b) where the loop gets deferred should an immediate move (an uncomputed offset)
           have been started,

        """
        
        if not self.guiding:
            self.stopGuiding()
            return

        if self.offsetWillBeDone > 0.0:
            diff = self.offsetWillBeDone - time.time()
            if diff > 0.0:
                self.cmd.warn('%sTxt="deferring guider frame for %0.2f seconds to allow immediate offset to finish"' % (self.controller.name, diff))
                time.sleep(diff)        # Yup. Better be short, hunh?
            self.offsetWillBeDone = 0.0
                
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
        
        Think about a dead zone, or a scaling function that decreases close to the boresight.
        """

        fitErrors = star.err
        
        scales = self.tweaks['fitErrorScale']
        scales.reverse()
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

        self.cmd.warn('debug="boresight is at (%0.2f, %0.2f)"' % (xPos, yPos))
        return xPos, yPos

    def _getExpectedPos(self, t=None):
        """ Return the expected position of the guide star in GPos coordinates. """

        if self.guidingType == 'field':
            pvt = self._ICRS2GPos(self.PVT2pos(self.refPVT, t=t))
            return self.PVT2pos(pvt, t=t)
        else:
            return self.getBoresight(t)

    def _genOffsetCmd(self, cmd, star, frame, refGpos, offsetType='guide', doScale=True, fname=''):
        """ Generate the TCC offset command between the given star and refGpos
        
        Args:
            cmd        - the command that controls us.
            star       - the star that we wwant to move.
            frame      - the ImageFrame that star the embedded in.
            refGpos    - the position to move to/towards
            offsetType - 'guide' or 'calibration'
            doScale    - if True, filter the offset according to self.tweaks
        """

        # We know the boresight pixel .boresightPixel and the source pixel fromPixel.
        #  - Convert each to Observed positions
        #
        now = time.time()
        refPVT = self._GPos2Obs(refGpos)
        starPVT = self._GPos2Obs(star.ctr)
        
        if not refPVT \
           or not starPVT \
           or None in refPVT \
           or None in starPVT:
            self.failGuiding("Could not convert a coordinate")
            return ''

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

        #  - Generate the offset. Threshold computed & uncomputed
        #
        diffSize = math.sqrt(diffPos[0] * diffPos[0] + diffPos[1] * diffPos[1])
        flag = ''
        if diffSize > (CPL.cfg.get('telescope', 'maxUncomputedOffset', default=10.0) / (60*60)):
            flag += "/computed"

        if diffSize <= (self.tweaks.get('minOffset', 0.1) / (60*60)):
            self.cmd.warn('%sDebug=%s' % \
                                 (self.controller.name,
                                  CPL.qstr('SKIPPING diff=%0.6f,%0.6f' % (diffPos[0],
                                                                          diffPos[1]))))
            return ''


        self.cmd.warn('debug=%s' % (CPL.qstr('offset=%0.2f,%0.2f act=%0.2f,%0.2f file=%s' % \
                                             (baseDiffPos[0] * 3600, baseDiffPos[1] * 3600,
                                              diffPos[0] * 3600, diffPos[1] * 3600,
                                              fname))))
            
        # Offsets are by default relative.
        #
        cmdTxt = 'offset %s %0.6f,%0.6f %s' % (offsetType, diffPos[0], diffPos[1], flag)
        return cmdTxt
    
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

        cmdTxt = self._genOffsetCmd(cmd, star, frame, refGpos, offsetType, doScale, fname=fname)
        if self.cmd.argDict.has_key('noMove') or not cmdTxt:
            self.cmd.warn('%sTxt="NOT sending tcc %s"' % (self.controller.name, cmdTxt))
            self._guideLoopTop()
        else:
            self.cmd.warn('debug=%s' % (CPL.qstr('starting offset: %s' % (cmdTxt))))
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

        if self.trackFilename == None:
            self.cmd.warn('debug=%s' % (CPL.qstr("tracking filenames from %s" % (startName))))
            self.trackFilename = startName
            return startName

        filename, ext = os.path.splitext(self.trackFilename)
        basename = filename[:-4]
        idx = int(filename[-4:], 10)
        idx += 1

        newname = "%s%04d%s" % (basename, idx, ext)
        self.trackFilename = newname

        self.cmd.warn('debug=%s' % (CPL.qstr("tracked filename: %s" % (newname))))

        return newname
        
    def _handleGuiderFrame(self, cmd, filename, frame, tweaks=None):
        """ Given a new guider frame, calculate and apply the Guide offset and launch
        a new guider frame.
        """

        if not self.guiding:
            self.stopGuiding()
            return
        
        self.cmd.warn('debug=%s' % (CPL.qstr('new guide camera file=%s, frame=%s' % \
                                             (filename, frame))))

        if self.telHasBeenMoved:
            self.cmd.warn('txt=%s' % \
                          (CPL.qstr("guiding deferred: %s" % (self.telHasBeenMoved))))
            self.telHasBeenMoved = False
            self._guideLoopTop()
            return
        
        if self.cmd.argDict.has_key('file'):
            filename = self.getNextTrackedFilename(self.cmd.argDict['file'])
        frame = GuideFrame.ImageFrame(self.controller.size)
        frame.setImageFromFITSFile(filename)

        # We need the maskfile name for the guiderFiles keyword.
        maskName, maskbits = self.controller.mask.getMaskForFrame(cmd, filename, frame)

        self.controller.genFilesKey(self.cmd, 'g', True,
                                    filename, maskName, None, None, filename)
        
        # Need to interpolate to the middle of the exposure.
        now = time.time()
        refPos = self._getExpectedPos(t=now)
        self.cmd.respond("guiderPredPos=%0.2f,%0.2f" % (refPos[0], refPos[1]))
        try:
            star = MyPyGuide.centroid(self.cmd, filename, self.controller.mask,
                                      frame, refPos, tweaks=self.tweaks)
            if not star:
                raise RuntimeError('no star found')
        except RuntimeError, e:
            self.failGuiding(e)
            return

        # Get the other stars in the field
        try:
            isSat, stars = MyPyGuide.findstars(self.cmd, filename, self.controller.mask,
                                               frame, tweaks=self.tweaks)
        except RuntimeError, e:
            stars = []
            
        MyPyGuide.genStarKey(cmd, star, caller='c')
        if stars:
            MyPyGuide.genStarKeys(cmd, stars, caller='f')
            
        self.cmd.warn('debug=%s' % (CPL.qstr('center=%0.2f, %0.2f' % (star.ctr[0],
                                                                      star.ctr[1]))))
        self._centerUp(self.cmd, star, frame, refPos, fname=filename)
        
    def _extractCnvPos(self, res):
        """ Extract and convert the converted position from a tcc convert.

        Returns:
           P,V,T, P2,V2,T2
           
        Makes no attempt to handle velocities.
        """

        cvtPos = res.KVs.get('ConvPos', None)
        # self.cmd.respond('debugTxt=%s' % (CPL.qstr('cnvPos=%s' % (cvtPos))))

        if cvtPos == None:
            return None * 6
        else:
            try:
                cvtPos = map(float, cvtPos)
            except Exception, e:
                self.cmd.warn("txt=%s" % \
                              (CPL.qstr("Failed to parse CONVERT output: %r" % (cvtPos))))
                return None * 6
                
            return cvtPos

    def _checkCoordinates(self, pos):
        """ Check whether pos is a valid pair of valid coordinates. """

        if "%s" % pos[0] == 'nan' or "%s" % pos[1] == 'nan':
            raise RuntimeError('undefined coordinates')
        
        
    def _GPos2ICRS(self, pos):
        """ Convert a Guide frame coordinate to an ICRS coordinate. """        

        # self.cmd.respond('debug=%s' % (CPL.qstr("gpos2ICRS pos=%r" % (pos,))))

        self._checkCoordinates(pos)
        ret = client.call("tcc", "convert %0.5f,%0.5f gimage icrs" % (pos[0], pos[1]),
                          cid=self.controller.cidForCmd(self.cmd))
        return self._extractCnvPos(ret)
    
    def _GPos2Obs(self, pos):
        """ Convert a Guide frame coordinate pair to an Observed coordinate pair.

        Args:
            pos   - pos1,pos2

        Returns:
            cvtpos1, cvtpos2
        """

        # self.cmd.respond('debug=%s' % (CPL.qstr("gpos2Obs pos=%r" % (pos,))))        
        self._checkCoordinates(pos)

        ret = client.call("tcc", "convert %0.5f,%0.5f gimage obs" % (pos[0], pos[1]),
                          cid=self.controller.cidForCmd(self.cmd))
        return self._extractCnvPos(ret)
    
    def _ICRS2Obs(self, pos):
        """ Convert an ICRS coordinate to an Observed coordinate. """

        # self.cmd.respond('debug=%s' % (CPL.qstr("ICRS2Obs pos=%r" % (pos,))))        
        self._checkCoordinates(pos)

        ret = client.call("tcc", "convert %0.5f,%0.5f icrs obs" % (pos[0], pos[1]),
                          cid=self.controller.cidForCmd(self.cmd))
        return self._extractCnvPos(ret)

    def _ICRS2GPos(self, pos):
        """ Convert an ICRS coordinate to a guider frame coordinate. """

        # self.cmd.respond('debug=%s' % (CPL.qstr("ICRS2GPos pos=%r" % (pos,))))        
        self._checkCoordinates(pos)

        ret = client.call("tcc", "convert %0.5f,%0.5f icrs gimage" % (pos[0], pos[1]),
                          cid=self.controller.cidForCmd(self.cmd))
        return self._extractCnvPos(ret)
    
