__all__ = ['GuideLoop']

import math
import os
import time

import client
import CPL
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
        # may not be valid.
        #
        self.telHasBeenMoved = False
        self.offsetWillBeDone = 0.0

        # What to add to TCC times to get Unix seconds
        self.tccDtime = -3506716800.0 - 32.0

        client.listenFor('tcc', ['MoveItems', 'Moved'], self.listenToMoveItems)
        client.listenFor('tcc', ['TCCStatus'], self.listenToTCCStatus)
        client.listenFor('tcc', ['Boresight'], self.listenToTCCBoresight)
        client.listenFor('tcc', ['GImCtr'], self.listenToTCCImCtr)
        client.listenFor('tcc', ['GImScale'], self.listenToTCCImScaler)

        # Force a couple of updates:
        client.call("tcc", "show inst/full") # ImCtr, ImScale
        client.call("tcc", "show object") # Boresight
        
    def failGuiding(self, why):
        """ Stop guiding, 'cuz something went wrong.
        This must only be called when the loop has stopped.
        """

        self.cmd.respond('guiding=%s' % CPL.qstr(self.guiding))
        self.cmd.fail('%sTxt=%s' % (self.controller.name, CPL.qstr(why)))
        self.controller.guideLoopIsStopped()

    def stopGuiding(self):
        """ Stop guiding, on purpose
        This must only be called when the loop has stopped.
        """

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
        if mi[7] == 'Y':
            self.telHasBeenMoved = 'Guide offset was changed'
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
        pos = list(map(float, k))
        if k[2] != 'NaN':
            pos[2] += self.tccDtime
        if k[5] != 'NaN':
            pos[5] += self.tccDtime

        self.boresightOffset = pos
    
    def listenToTCCImCtr(self, reply):
        """ Set the guider/instrument center pixel.
        """

        k = reply.KVs['GImCtr']
        self.boresight = map(float, k)
        
    def listenToTCCImScale(self, reply):
        """ Set the guider/instrument scales.
        """

        k = reply.KVs['GImScale']
        self.imScale = map(float, k)
        
    def getBoresight(self, t=None):
        """ Figure out the boresight position for a given time.

        The effective boresight is the sum of the instrument/guider center and the
        boresight offset. 

        Args:
             T       - time, in Unix seconds, to reckon the boresight at.
        """

        if t == None:
            t = time.time()

        xPos = self.boresight[0] + \
               self.imScale[0] * (self.boresightOffset[0] + \
                                  (t - self.boresightOffset[2]) * self.boresightOffset[1])
        yPos = self.boresight[1] + \
               self.imScale[1] * (self.boresightOffset[3] + \
                                  (t - self.boresightOffset[5]) * self.boresightOffset[4])

        return xPos, yPos
    
    def _doGuide(self):
        """ Actually start guiding.

        Examines parts of the .tweaks dictionary for several things:
           time     - seconds to expose

           guideStar=X,Y   - the position to start centroiding on.
        or:
           centerFrom=X,Y  - the position of a star to move to the boresight.

        If neither is specified, run a findstars and guide on the "best" return.
        """

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
            # Simply start nudging the nearest object to the boresight to the boresight
            #
            self.guidingType = 'boresight'
            self.refpos = self._GPos2ICRS(self.getBoresight())
        elif centerOn:
            # if "centerOn" is specified, offset the given position to the boresight,
            # then continue nudging it there.
            #
            self.guidingType = 'boresight'
            seedPos = self.controller.parseCoord(centerOn)

            self.cmd.respond('txt="offsetting object to the boresight...."')
            try:
                star = MyPyGuide.centroid(self.cmd, filename, self.controller.mask,
                                          frame, seedPos, self.tweaks)
                if not star:
                    raise RuntimeError('no star found near (%d, %d)' % seedPos)
            except RuntimeError, e:
                self.failGuiding(e)
                return

            self.refpos = self._GPos2ICRS(self.getBoresight())
            ret = self._centerUp(cmd, star, scaleFunc=None, offsetType='calib')
            if not ret:
                self.failGuiding('could not move the specified object to the boresight.')
                return
            
        elif gstar:
            # if "gstar" is specified, use that as the guide star.
            #
            seedPos = self.controller.parseCoord(gstar)
            try:
                star = MyPyGuide.centroid(self.cmd, filename, self.controller.mask,
                                          frame, seedPos, self.tweaks)
                if not star:
                    raise RuntimeError('no star found near (%d, %d)' % seedPos)
            except RuntimeError, e:
                self.failGuiding(e)
                return

            self.guidingType = 'field'
            self.refpos = self._GPos2ICRS(star.ctr)
        else:
            # otherwise use the "best" object as the guide star.
            #
            isSat, stars = MyPyGuide.findstars(self.cmd, filename, self.controller.mask,
                                               frame, self.tweaks)
            if not stars:
                self.failGuiding("no stars found")
                return

            startPos = stars[0].ctr
            self.guidingType = 'field'
            self.refpos = self._GPos2ICRS(startPos)

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
        
    def scaleOffset(self, star, diffPos)
        """ Scale the effective offset.

        Args:
            star          - star info, including s.ctr and error estimates
            diffPos       - the original offset.
            
        Think about a dead zone, or a scaling function that decreases close to the boresight.
        """

        fitErrors = star.err
        
        scales = self.tweaks['fitErrorScale']
        scales.reverse()
        xfitFactor = 0.0
        for scale in scales:
            if fitErrors[0] < scale[0]:
                xfitFactor = scale[1]
                break
        yfitFactor = 0.0
        for scale in scales:
            if fitErrors[1] < scale[0]:
                yfitFactor = scale[1]
                break
            
        return [diffPos[0] * xfitFactor, \
               diffPos[1] * yfitFactor]

    def _getExpectedPos(self, t=None):
        """ Return the expected position of the guide star. """

        if self.guidingType == 'field':
            return self._ICRS2GPos(self.refpos)
        else:
            return self.getBoresight(t)

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


    def _getRefPosition(self):
        """ Return the current reference position in alt/az -- the position
        we want to be at. """

        if self.guidingType == 'field':
            return self._ICRS2Obs(self.refpos)
        else:
            return self._GPos2Obs(self.getBoresight())
    
    def _centerUp(self, cmd, star, refGpos, offsetType='guide', doScale=True):
        """ Move the given star to/towards the ref pos.
        
        Args:
            cmd        - the command that controls us.
            star       - the star that we wwant to move.
            refGpos    - the position to move to/towards
            offsetType - 'guide' or 'calibration'
            doScale    - if True, filter the offset according to self.tweaks
        """

        # We know the boresight pixel .boresightPixel and the source pixel fromPixel.
        #  - Convert each to Observed positions
        #
        refPos = self._GPos2Obs(refGpos)
        starPos = self._GPos2Obs(star.ctr)
        
        if not refPos \
           or not starPos \
           or None in refPos \
           or None in starPos:
            self.failGuiding("Could not convert a coordinate")
            return False

        trailOffset = self._getTrailOffset()
        refPos = [refPos[0] + trailOffset[0],
                  refPos[1] + trailOffset[1]]
        
        #  - Diff the Observed positions
        #
        diffPos = [starPos[0] - refPos[0], \
                   starPos[1] - refPos[1]]

        if doScale:
            diffPos = self.scaleOffset(cmd, star, diffPos)

        #  - Generate the offset. Threshold computed & uncomputed
        #
        diffSize = math.sqrt(diffPos[0] * diffPos[0] + diffPos[1] * diffPos[1])
        flag = ''
        if diffSize > (CPL.cfg.get('telescope', 'maxUncomputedOffset', default=10.0) / (60*60)):
            flag += "/computed"

        if diffSize <= (self.tweaks.get('minOffset', 0.15) / (60*60)):
            self.cmd.warn('%sDebug=%s' % \
                                 (self.controller.name,
                                  CPL.qstr('SKIPPING diff=%0.6f,%0.6f' % (diffPos[0],
                                                                          diffPos[1]))))
            return True
        
        self.cmd.warn('%sDebug=%s' % (self.controller.name,
                                             CPL.qstr('diff=%0.6f,%0.6f' % (diffPos[0],
                                                                            diffPos[1]))))
        # Offsets are by default relative.
        #
        cmd = 'offset %s %0.6f,%0.6f %s' % (offsetType, diffPos[0], diffPos[1], flag),

        if self.cmd.argDict.has_key('noMove'):
            cmd.warn('%sTxt="NOT sending tcc %s"' % (self.controller.name, cmd))
        else:
            client.call('tcc', cmd, cid=self.controller.cidForCmd(cmd))

        return True

    def getNextTrackedFilename(self, startName):
        """ If our command requests a filename, we need to read a sequence of files.
        """

        if self.trackFilename == None:
            self.trackFilename = startName
            return startName

        filename, ext = os.path.splitext(self.trackFilename)
        basename = filename[:-4]
        idx = int(filename[-4:], 10)
        idx += 1

        newname = "%s%04d%s" % (basename, idx, ext)
        self.trackFilename = newname

        return newname
        
    def _handleGuiderFrame(self, cmd, filename, frame):
        """ Given a new guider frame, calculate and apply the Guide offset and launch
        a new guider frame.
        """

        if not self.guiding:
            self.stopGuiding()
            return
        
        self.cmd.warn('%sDebug=%s' % (self.controller.name,
                                      CPL.qstr('new file=%s, frame=%s' % \
                                               (filename, frame))))

        if self.telHasBeenMoved:
            self.cmd.warn('%sTxt=%s' % \
                          (CPL.qstr("guiding deferred: %s" % (self.telHasBeenMoved))))
            self.telHasBeenMoved = False
            self._guideLoopTop()
            return
        
        if self.cmd.argDict.has_key('file'):
            fname = self.getNextTrackedFilename(self.cmd.argDict['file'])
        else:                           # USE res.KVs['imgFile']!
            fname = self.controller.camera.getLastImageName(self.cmd)

        # Need to interpolate to the middle of the exposure.
        refPos = self._getExpectedPos(),
        try:
            star = MyPyGuide.centroid(self.cmd, fname, self.controller.mask,
                                      frame, refPos, tweaks=self.tweaks)
            if not star:
                raise RuntimeError('no star found')
        except RuntimeError, e:
            self.failGuiding(e)
            return

        self.cmd.warn('%sDebug=%s' % (self.controller.name,
                                      CPL.qstr('center=%0.2f, %0.2f' % (star.ctr[0],
                                                                        star.ctr[1]))))
        ret = self._centerUp(self.cmd, star, refPos)
        if not ret:
            self.failGuiding('could not offset')
            return
        
        self._guideLoopTop()
        
    def _extractCnvPos(self, res):
        """ Extract and convert the converted position from a tcc convert.

        Returns:
           pos1, pos2  - where pos1 & pos2 are the two fixed positions returned by convert.
           
        Makes no attempt to handle velocities.
        """

        self.cmd.respond('%sDebug=%s' % (self.controller.name,
                                                CPL.qstr('cnvPos ret = %s' % repr(res))))

        cvtPos = res.KVs.get('ConvPos', None)
        if cvtPos == None:
            return None, None
        else:
            try:
                cvtPos = map(float, cvtPos)
            except Exception, e:
                self.cmd.warn("%sTxt=%s" % \
                                     (CPL.qstr("Failed to parse CONVERT output: %r" % (cvtPos))))
                return None, None
                
            return cvtPos[0], cvtPos[3]
    
    def _GPos2ICRS(self, pos):
        """ Convert a Guide frame coordinate to an ICRS coordinate. """        
        
        self.cmd.respond('%sDebug=%s' % (self.controller.name,
                                                CPL.qstr("gpos2ICRS pos=%r" % (pos,))))
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

        self.cmd.respond('%sDebug=%s' % (self.controller.name,
                                                CPL.qstr("gpos2Obs pos=%r" % (pos,))))        
        ret = client.call("tcc", "convert %0.5f,%0.5f gimage obs" % (pos[0], pos[1]),
                          cid=self.controller.cidForCmd(self.cmd))
        return self._extractCnvPos(ret)
    
    def _ICRS2Obs(self, pos):
        """ Convert an ICRS coordinate to an Observed coordinate. """

        self.cmd.respond('%sDebug=%s' % (self.controller.name,
                                                CPL.qstr("ICRS2Obs pos=%r" % (pos,))))        
        ret = client.call("tcc", "convert %0.5f,%0.5f icrs obs" % (pos[0]. pos[1]),
                          cid=self.controller.cidForCmd(self.cmd))
        return self._extractCnvPos(ret)

    def _ICRS2GPos(self, pos):
        """ Convert an ICRS coordinate to a guider frame coordinate. """

        self.cmd.respond('%sDebug=%s' % (self.controller.name,
                                                CPL.qstr("ICRS2Obs pos=%r" % (pos,))))        
        ret = client.call("tcc", "convert %0.5f,%0.5f icrs gimage" % (pos[0]. pos[1]),
                          cid=self.controller.cidForCmd(self.cmd))
        return self._extractCnvPos(ret)
    
