__all__ = ['GuideLoop']

import math

import client
import CPL
from PyGuide import Centroid, FindStars

class GuideLoop(object):

    def _doGuide(self, cmd):
        """ Actually start guiding.

        CmdArgs:
           time     - seconds to expose

        Optional CmdArgs:
           on=X,Y        - the position to start centroiding on.
           center        - move the starting centroid to the boresight.
           boresight=X,Y - the pixel to 

        If no center (on=) is specified, run a findstars and guide on the "best" return.
        """

        assert self.guidingCmd == None, "guidingCmd exists"
        
        self.guidingCmd = cmd
        self.guiding = True

        self.trailingOffset = 0.0
        self.trailingLimit = 1.5 / (60*60)
        self.trailingStep = 0.5 / (60*60)
        self.trailingSkip = 1
        self.trailingDir = 1
        self.trailingN = 0
        
        # Steps:
        #  1) get a starting position startPos:
        #      a) if specified, use on= position to seed centroid()
        #      b) or call findstars() and use 'best' position
        #
        fname = self._doCmdExpose(cmd, 'expose', 'guide')

        on = cmd.argDict.get('on')
        if on == None:
            if cmd.argDict.has_key('lie'):
                rawLie = cmd.argDict['lie']
                startPos = [float(rawLie[0]),
                             float(rawLie[1])]
            else:
                startPos = self._getBestCenter(cmd, fname)
        else:
            seedPos = self.parseCoord(on)
            try:
                startPos, counts, points = self._doCentroid(cmd, seedPos, fname)
            except RuntimeError, e:
                self.failGuiding(e)
                return

        if not startPos:
            self.failGuiding("no stars found")
            return
        
        #  2) adjust boresight, if requested.
        #
        boresight = cmd.argDict.get('boresight')
        if boresight:
            boresightPos = self.parseCoord(boresight)
            # client.call('tcc', 'offset xxxxx')

        #  3) if "center" is specified, offset startPos to boresight.
        #
        if cmd.argDict.has_key('center'):
            ret = self._centerUp(cmd, startPos, doScale=False)
            if not ret:
                return
            
        #  4) start the guiding loop:
        #
        self.guidingCmd.respond('%sGuiding=True' % (self.name))
        self._guideLoopTop()
        
    def _guideLoopTop(self):
        if self.guiding == False:
            self.stopGuiding()
            return

        self._doCmdExpose(self.guidingCmd, 'expose', 'guide', callback=self._handleGuiderFrame)
        
    def _scaleOffsets(self, cmd, diffPos):
        """ Scale the effective offset.

        Use a global scale to keep from overguiding.
        Think about a dead zone, or a scaling function that decreases close to the boresight.
        """

        return [diffPos[0] * self.guideScale, \
               diffPos[1] * self.guideScale]

    def _getExpectedPos(self):
        """ Return the expected position of the guide star. """

        return self.boresightPixel
    
    def _getTrailOffset(self, cmd):
        """ Return the next trailing offset, in degrees. """

        if not cmd.argDict.has_key('trail'):
            return [0.0, 0.0]
        
        # Move .trailingStep each offset we take. When we reach the end (.trailingLimit),
        # turn around.
        #
        if abs(self.trailingOffset) >= self.trailingLimit:
            self.trailingDir *= -1
            
        self.trailingOffset += self.trailingDir * self.trailingStep

        return [0.0, self.trailingOffset]


    def _getRefPosition(self, cmd):
        """ Return the current reference position in pixels -- the position
        we want to be at. """

        return self.boresightPixel
    
    def _centerUp(self, cmd, fromPixel, doScale=True):
        """ Move fromPixel to the boresight using Guide offsets.

        Args:
            cmd        - the command that controls us.
            fromPixel  - the position to offset from.
            doScale    - whether to filter the offsets through some control function.
            
        """

        # We know the boresight pixel .boresightPixel and the source pixel fromPixel.
        #  - Convert each to Observed positions
        #
        refPos = self._GPos2Obs(self._getRefPosition(cmd))
        fromPos = self._GPos2Obs(fromPixel)

        if not refPos \
           or not fromPos \
           or None in refPos \
           or None in fromPos:
            self.failGuiding("Could not convert a coordinate")
            return False

        trailOffset = self._getTrailOffset(cmd)
        refPos = [refPos[0] + trailOffset[0],
                  refPos[1] + trailOffset[1]]
        
        #  - Diff the Observed positions
        #
        diffPos = [fromPos[0] - refPos[0], \
                  fromPos[1] - refPos[1]]

        if doScale:
            diffPos = self._scaleOffsets(cmd, diffPos)

        #  - Generate the offset. Threshold computed & uncomputed
        #
        diffSize = math.sqrt(diffPos[0] * diffPos[0] + diffPos[1] * diffPos[1])
        flag = ''
        if diffSize > (20.0 / (60*60)):
            flag = "/computed"

        if diffSize <= (0.3 / (60*60)):
            self.guidingCmd.warn('%sDebug=%s' % \
                                 (self.name,
                                  CPL.qstr('SKIPPING diff=%0.6f,%0.6f' % (diffPos[0],
                                                                          diffPos[1]))))
            return True
        
        self.guidingCmd.warn('%sDebug=%s' % (self.name,
                                             CPL.qstr('diff=%0.6f,%0.6f' % (diffPos[0],
                                                                            diffPos[1]))))
        # Offsets are by default relative.
        #
        if not self.guidingCmd.argDict.has_key('noMove'):
            client.call('tcc', 'offset guide %0.6f,%0.6f %s' % (diffPos[0], diffPos[1], flag),
                        cid=self.cidForCmd(cmd))

        return True

    def _handleGuiderFrame(self, res):
        """ Given a new guider frame, calculate and apply the Guide offset and launch
        a new guider frame.
        """

        self.guidingCmd.warn('%sDebug=%s' % (self.name,
                                             CPL.qstr('new frame=%s' % (res))))

        if self.guidingCmd.argDict.has_key('file'):
            fname = self.guidingCmd.argDict['file']
        else:
            fname = self.camera.getLastImageName(self.guidingCmd)

        if self.guidingCmd.argDict.has_key('lie'):
            rawLie = self.guidingCmd.argDict['lie']
            actualPos = [float(rawLie[0]),
                         float(rawLie[1])]
            self.guidingCmd.warn('%sDebug=%s' % (self.name,
                                                 CPL.qstr('lie=%s' % (actualPos))))
        else:
            try:
                actualPos, counts, points = self._doCentroid(self.guidingCmd,
                                                             self._getExpectedPos(),
                                                             fname)
            except RuntimeError, e:
                self.failGuiding(e)
                return

        self.guidingCmd.warn('%sDebug=%s' % (self.name,
                                             CPL.qstr('center=%0.2f, %0.2f' % (actualPos[0],
                                                                               actualPos[1]))))
        if not actualPos:
            self.failGuiding('no star found')
            return

        ret = self._centerUp(self.guidingCmd, actualPos)
        if not ret:
            return
        
        self._guideLoopTop()
        
    def _guiderCallback(self, res):
        """ Accept a completed guider exposure.

        If .guiding is False, ignore the result and finish out .guidingCmd.
        If .guiding is True, call the .handleGuiderFrame hook with the new frame.
        """

        if self.guiding == False:
            self.guidingCmd.finish('%sGuiding=False' % (self.name))
            self.guidingCmd = None
            return


        self.handleGuiderFrame(self, res)

    def _getKeyFromResponse(self, res, key, _cvt=None):
        """  Return the value for a key by rooting around in a command response. 
        """

        val = None
        lines = res['lines']
        lines.reverse()
        
        for l in lines:
            if key in l:
                v = l[key]
                if _cvt:
                    return _cvt(v)
                else:
                    return v
            
    def _extractCnvPos(self, res):
        """ Extract and convert the converted position from a tcc convert. """

        self.guidingCmd.respond('%sDebug=%s' % (self.name,
                                                CPL.qstr('cnvPos ret = %s' % repr(res))))

        cvtPos = self._getKeyFromResponse(res, 'ConvPos')
        if cvtPos == None:
            return None, None
        else:
            try:
                cvtPos = map(float, cvtPos)
            except Exception, e:
                self.guidingCmd.warn("%sTxt=%s" % \
                                     (CPL.qstr("Failed to parse CONVERT output: %r" % (cvtPos))))
                return None, None
                
            return cvtPos[0], cvtPos[3]
    
    def _GPos2ICRS(self, pos):
        self.guidingCmd.respond('%sDebug=%s' % (self.name,
                                                CPL.qstr("gpos2 pos=%r" % (pos,))))
        ret = client.call("tcc", "convert %0.3f,%0.3f gimage icrs" % (pos[0], pos[1]),
                          cid=self.cidForCmd(self.guidingCmd))
        return self._extractCnvPos(ret)
    
    def _GPos2Obs(self, pos):
        self.guidingCmd.respond('%sDebug=%s' % (self.name,
                                                CPL.qstr("gpos2 pos=%r" % (pos,))))        
        ret = client.call("tcc", "convert %0.3f,%0.3f gimage obs" % (pos[0], pos[1]),
                          cid=self.cidForCmd(self.guidingCmd))                          
        return self._extractCnvPos(ret)
    
    def _ICRS2Obs(self, pos):
        ret = client.call("tcc", "convert %0.3f,%0.3f icrs obs" % (pos[0]. pos[1]),
                          cid=self.cidForCmd(self.guidingCmd))                          
        return self._extractCnvPos(ret)
    
    def _guideOffset(self):
        raise NotImplementedError("_guideOffset not implemented")
    
    def _guideExpose(self):
        raise NotImplementedError("_guideExpose not implemented")
    


    
    
