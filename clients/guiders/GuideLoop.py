__all__ = ['GuideLoop']

import math
import os
import time

import client
import CPL
from PyGuide import Centroid, FindStars

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
        self.gstar = None
        
        # If we are "guiding" on a file sequence, track the sequence here.
        self.trackFilename = None
        
        self._initTrailing()

        # We listen for changes in TCC keywords that indicate that a guider frame
        # may not be valid.
        #
        self.telHasBeenMoved = False
        self.offsetWillBeDone = 0.0
        client.listenFor('tcc', ['MoveItems', 'Moved'], self.listenToMoveItems)
        client.listenFor('tcc', ['TCCStatus'], self.listenToTCCStatus)

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
        
    def stop(self):
        """ A way for the outside world to stop the loop.

        This merely sets a flag that other parts of the loop examine at appropriate times.
        """
        
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
            self.stop()
        if 'S' in axisStat:
            self.telHasBeenMoved = 'Telescope was slewed'
    
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

        # Steps:
        #  1) Look for at-start offsets (centerOn=X,Y or gstar=X,Y
        #      if specified, use specified position to seed centroid()
        #      then move the result to the boresight.
        #
        fname = self.controller._doCmdExpose(self.cmd, 'expose', 'guide')

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
        elif centerOn:
            # if "centerOn" is specified, offset the given position to the boresight,
            # then continue nudging it there.
            #
            self.guidingType = 'boresight'
            seedPos = self.controller.parseCoord(centerOn)

            self.cmd.respond('%sTxt="offsetting object to the boresight...."' % (self.controller.name))
            try:
                startPos, counts, points = self.controller._doCentroid(self.cmd, seedPos, fname)
            except RuntimeError, e:
                self.failGuiding(e)
                return

            ret = self._centerUp(cmd, startPos, scaleFunc=None, offsetType='calib')
            if not ret:
                self.failGuiding('could not move the specified object to the boresight.')
                return
            
        elif gstar:
            # if "gstar" is specified, use that as the guide star.
            #
            seedPos = self.controller.parseCoord(gstar)
            try:
                startPos, counts, points = self.controller._doCentroid(cmd, seedPos, fname)
            except RuntimeError, e:
                self.failGuiding(e)
                return

            self.guidingType = 'field'
            self.gstar = self._GPos2ICRS(startPos)
        else:
            # otherwise use the "best" object as the guide star.
            #
            startPos = self.controller._getBestCenter(self.cmd, fname)
            if not startPos:
                self.failGuiding("no stars found")
                return

            self.guidingType = 'field'
            self.gstar = self._GPos2ICRS(startPos)
        

        #  4) start the guiding loop:
        #
        self.cmd.respond('%sGuiding=True' % (self.controller.name))
        self._guideLoopTop()
        
    def _guideLoopTop(self):
        """ The "top" of the guiding loop.

        This is
           a) one place where the loop gets stopped and
           b) where the loop gets deferred should an immediate move (an uncomputed offset)
           have been started,

        """
        
        if self.guiding == False:
            self.stopGuiding()
            return

        if self.offsetWillBeDone > 0.0:
            diff = self.offsetWillBeDone - time.time()
            if diff > 0.0:
                self.cmd.warn('%sTxt="deferring guider frame for %0.2f seconds to allow immediate offset to finish"' % (self.controller.name, diff))
                time.sleep(diff)        # Yup. Better be short, hunh?
            self.offsetWillBeDone = 0.0
                
        self.controller._doCmdExpose(self.cmd, 'expose', 'guide', callback=self._handleGuiderFrame)
        
    def _scaleOffsets(self, diffPos, fitErrors, chiSqErrors):
        """ Scale the effective offset.

        Args:
            diffPos       - the original offset.
            fitErrors     - the estimated errors.
            chiSqErrors   - the chiSq fits errors. CURRENTLY IGNORED
            
        Think about a dead zone, or a scaling function that decreases close to the boresight.
        """

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

    def _getExpectedPos(self):
        """ Return the expected position of the guide star. """

        if self.guidingType == 'field':
            return self._ICRS2GPos(self.gstar)
        else:
            return self.tweaks['boresightPixel']

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
            return self._ICRS2Obs(self.gstar)
        else:
            return self._GPos2Obs(self.tweaks['boresightPixel'])
    
    def _centerUp(self, cmd, fromPixel, scaleFunc=None, offsetType='guide'):
        """ Move fromPixel to the boresight using either guide or calibration offsets.

        Args:
            cmd        - the command that controls us.
            fromPixel  - the pixel to offset from.
            scaleFunc  - a filter to adjust the offsets.
            offsetType - 'guide' or 'calibration'
        """

        # We know the boresight pixel .boresightPixel and the source pixel fromPixel.
        #  - Convert each to Observed positions
        #
        refPos = self._getRefPosition()
        fromPos = self._GPos2Obs(fromPixel)
        
        if not refPos \
           or not fromPos \
           or None in refPos \
           or None in fromPos:
            self.failGuiding("Could not convert a coordinate")
            return False

        trailOffset = self._getTrailOffset()
        refPos = [refPos[0] + trailOffset[0],
                  refPos[1] + trailOffset[1]]
        
        #  - Diff the Observed positions
        #
        diffPos = [fromPos[0] - refPos[0], \
                  fromPos[1] - refPos[1]]

        if scaleFunc:
            diffPos = scaleFunc(cmd, diffPos)

        #  - Generate the offset. Threshold computed & uncomputed
        #
        diffSize = math.sqrt(diffPos[0] * diffPos[0] + diffPos[1] * diffPos[1])
        flag = ''
        if diffSize > (CPL.cfg.get('telescope', 'maxUncomputedOffset', default=20.0) / (60*60)):
            flag += "/computed"

        if diffSize <= (self.tweaks.get('minOffset', 0.2) / (60*60)):
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
        
    def _handleGuiderFrame(self, res):
        """ Given a new guider frame, calculate and apply the Guide offset and launch
        a new guider frame.
        """

        if not self.guiding:
            self.stopGuiding()
            return
        
        self.cmd.warn('%sDebug=%s' % (self.controller.name,
                                      CPL.qstr('new frame=%s' % (res))))

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

        if self.guidingType == 'field':
            seedPos = self._ICRS2GPos(self.gstar)
        else:
            seedPos = self._getExpectedPos(),

        try:
            actualPos, counts, points = self.controller._doCentroid(self.cmd,
                                                                    seedPos,
                                                                    fname)
        except RuntimeError, e:
            self.failGuiding(e)
            return

        self.cmd.warn('%sDebug=%s' % (self.controller.name,
                                      CPL.qstr('center=%0.2f, %0.2f' % (actualPos[0],
                                                                        actualPos[1]))))
        if not actualPos:
            self.failGuiding('no star found')
            return

        ret = self._centerUp(self.cmd, actualPos)
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
    
