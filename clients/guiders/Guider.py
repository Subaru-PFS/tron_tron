#!/usr/bin/env python

__all__ = ['Guider']

""" The "guider" command.

"""

import inspect
import pprint
import sys
import traceback

import PyGuide
import pyfits
import Command
import Actor
import CPL
import GuideLoop
import GuiderMask

class Guider(Actor.Actor):
    """ The Guider class is expected to be subclassed for the specific guiders.
    """
    
    def __init__(self, camera, guiderName, **argv):
        """
        """
        
        Actor.Actor.__init__(self, guiderName, **argv)

        self.commands.update({'status':     self.doStatus,
                              'expose':     self.doExpose,
                              'dark':       self.doDark,
                              'centroid':   self.doCentroid,
                              'findstars':  self.doFindstars,
                              'init':       self.doInit,
			      'set':        self.doSet,
                              'setMask':    self.doSetMask,
                              'setScale':   self.doSetScale,
                              'setThresh':  self.doSetThresh,			      
                              'setBoresight': self.doSetBoresight,
                              'guide':      self.doGuide,
                              'zap':        self.doZap
                              })

        self.camera = camera
        self.activeExposure = None
        self.guideLoop = None
        self.mask = None

        self.defaults = {}
        self.defaults['starThresh'] = CPL.cfg.get(self.name, 'starThresh')
        self.defaults['guideScale'] = CPL.cfg.get(self.name, 'guideScale')
        self.defaults['scanRadius'] = CPL.cfg.get(self.name, 'scanRadius')
        self.defaults['maskFile'] = CPL.cfg.get(self.name, 'maskFile')
        
    def xy2ij(self, pos):
	""" Swap between (x,y) and image(i,j). """
        return pos[1], pos[0]

    def ij2xy(self, pos):
	""" Swap between image(i,j) and (x,y). """
        return pos[1], pos[0]


    def trimUnit(self, x, size):
	""" Trim a coordinate to [0..size], but do not change it's type. """
	
        if x < 0:
            if type(x) == int:
                return 0
            else:
                return 0.0
        if x > size:
            return size
        return x

    def trimCoord(self, x0, x1, size):
        """ Return the part of an extent that intersects a given [0..size-1]
        """

        return self.trimUnit(x0, size), self.trimUnit(x1, size)
        
    def trimRectToFrame(self, x0, y0, x1, y1, frameWidth, frameHeight):
        """ Return the section of a rectange that intersects a frame.

        Args:
             x0, y0         - the LL corner of a rectangle
             x1, y1         - the UR corner of a rectangle
             frameWidth,
             frameHeight    - the size of a frame.

        Returns:
             x0, y0         - the LL corner of a possibly trimmed rectangle
             x1, y1         - the UR corner of a possibly trimmed rectangle
        """

        tX0, tX1 = self.trimCoord(x0, x1, frameWidth)
        tY0, tY1 = self.trimCoord(y0, y1, frameHeight)

        CPL.log("rectTrim", "frame=%d,%d from=%s,%s,%s,%s to %s,%s,%s,%s" % \
                (frameWidth, frameHeight,
                 x0, y0, x1, y1,
                 tX0, tY0, tX1, tY1))

        return tX0, tY0, tX1, tY1
    
    def trimPosAndSizeToFrame(self, x0, y0, xSize, ySize, frameWidth, frameHeight):
        """ Return the section of a pos+size rectange that intersects a frame.

        Args:
             x0, y0         - the center of a rectangle
             xSize, ySize   - the size of a rectangle
             frameWidth,
             frameHeight    - the size of a frame.

        Returns:
             x0, y0         - the center of the possibly trimmed rectangle.
             xSize, ySize   - the size of the possibly trimmed rectangle
        """

        tX0, tY0, tX1, tY1 = self.trimRectToFrame(x0 - xSize/2.0, y0 - ySize/2.0,
                                                  x0 + xSize/2.0, y0 + ySize/2.0,
                                                  frameWidth, frameHeight) 

        return (tX1 + tX0) / 2, (tY1 + tY0) / 2, tX1-tX0, tY1-tY0
    
    
    def maskOutFromPosAndSize(self, mask, x0, y0, xSize, ySize, excludeRect=False):
        """ Given a mask, a position, and a size, return a mask with the given rectangle masked.

        Args:
            mask   - a mask numarray (1 == "masked", 0 == "unmasked")
            x0,y0  - a position
            xSize,ySize - a size
            excludeRect - if True, add the inverse of the rectange to the mask

        x0,y0 and xSize,ySize are forced onto the array.
        """

        if mask == None:
            return mask
        
        mYSize, mXSize = mask.getshape()

        tX0, tY0, tXSize, tYSize = self.trimPosAndSizeToFrame(x0, y0,
                                                              xSize, ySize,
                                                              mXSize, mYSize)
        CPL.log("maskTrim", "frame=%d,%d from=%s,%s,%s,%s to %s,%s,%s,%s" % \
                (mXSize, mYSize,
                 x0, y0, xSize, ySize,
                 tX0, tY0, tXSize, tYSize))
        
        mX0 = int(tX0 - tXSize/2.0)
        mX1 = int(tX0 + tXSize/2.0)
        mY0 = int(tY0 - tYSize/2.0)
        mY1 = int(tY0 + tYSize/2.0)
        if excludeRect:
            mask2 = mask.copy()
            mask2[0:mYSize,0:mXSize] = 1
            mask2[mY0:mY1+1,mX0:mX1+1] = 0
            mask |= mask2
        else:
            mask[mY0:mY1+1,mX0:mX1+1] = 1

        return mask
    
    def doStatus(self, cmd):
        """ Returns camera and guide loop status keywords. """

        self.camera.status(cmd)

        cmd.respond('maskFile=%s' % (CPL.qstr(self.maskFile)))
	
        if self.guideLoop:
            self.guideLoop.doStatus(cmd)

        cmd.finish("guiding=%s" % (CPL.qstr(self.guideLoop != None)))
    
    def doExpose(self, cmd):
        """ Take a single guider exposure and return it. This overrides but
        does not stop the guiding loop.
        """
        
        # Parse the arguments for the camera controller.
        #
        fname = self._doCmdExpose(cmd, 'expose', 'expose')
        cmd.respond('imgFile=%s' % (CPL.qstr(fname)))
        cmd.finish()
        
    doExpose.helpText = ('expose itime=S [window=X0,Y0,X1,Y1] [bin=N] [bin=X,Y]')

    def doDark(self, cmd):
        """ Take a single guider dark and return it. This overrides but
        does not stop the guiding loop.
        """

        fname = self._doCmdExpose(cmd, 'dark', 'dark')
        cmd.respond('imgFile=%s' % (CPL.qstr(fname)))
        cmd.finish()
        
    doDark.helpText = ('dark itime=S [window=X0,Y0,X1,Y1] [bin=N] [bin=X,Y]')

    def doFindstars(self, cmd):
        """ Takes a single guider exposure and runs findstars on it. This overrides but
        does not stop the guiding loop.
        """

        # Optionally handle the command as a GImCtrl
        if cmd.program() == 'TC01':
            return self.doTccFindstars(cmd)
            
        fname = self._doCmdExpose(cmd, 'expose', 'findstars')
        cmd.respond('%sDebug=%s' % (self.name, CPL.qstr('checking filename=%s' % (fname))))
        fits = pyfits.open(fname)
        img = fits[0].data
        fits.close()
        
        ds9 = cmd.argDict.get('ds9', False)
        # assert 1==0, "ds9 arg == %s" % (ds9)
	isSat, stars = PyGuide.findStars(
            data = img,
            mask=self.mask,
            ds9=ds9
	)

        if isSat:
            cmd.warn('%sFindstarsSaturated=%s' % (self.name, CPL.qstr(fname)))

        cmd.respond('%sFindstarsCnt=%d' % (self.name, len(stars)))
        i=1
        for counts, ctr, rad, totPts in stars:
            ctr = self.ij2xy(ctr)
            cmd.respond('%sFindstar=%d,%.1f,%.1f,%10.0f,%5.1f,%6d' % \
                        (self.name,
                         i,
                         ctr[0], ctr[1], counts, rad, totPts))
            i += 1
        cmd.finish()
        
    doFindstars.helpText = ('findstars itime=S [window=X0,Y0,X1,Y1] [bin=N] [bin=X,Y]')

    def doCentroid(self, cmd):
        """ Takes a single guider exposure and runs findstars on it. This overrides but
        does not stop the guiding loop.
        """

        # Optionally handle the command as a GImCtrl
        if cmd.program() == 'TC01':
            return self.doTccCentroid(cmd)
            
        fname = self._doCmdExpose(cmd, 'expose', 'centroid')

        if not cmd.argDict.has_key('on'):
            seed = self._getBestCenter(cmd, fname)
            if seed == None:
                cmd.fail('%sTxt="no stars found"' % (self.name))
                return
        else:
            seed = self.parseCoord(cmd.argDict['on'])
            

        centroid = self._doCentroid(cmd, seed, fname)
        shape = self._doStarShape(cmd, centroid.center,fname)
        measCtr = ij2xy(centroid.center)
        cmd.respond('centroid=%0.2f,%0.2f,%0.2f,%0.2f,%d,%d' % \
                    (measCtr[0], measCtr[1],
                     centroid.error[1], centroid.error[0], 
                     centroid.counts, centroid.pix))

        cmd.finish()
        return
    
        scanRad = float(cmd.argDict.get('rad', self.scanRad))
        cmd.respond('%sDebug=%s' % (self.name, CPL.qstr('centroid seed=%0.2f,%0.2f rad=%0.1f' % \
                                                        (seed[0], seed[1], scanRad))))
        fits = pyfits.open(fname)
        img = fits[0].data
        fits.close()

        ds9 = cmd.argDict.get('ds9', False)
	measCtr, nCounts, nPts = PyGuide.centroid(img,
                                                  self.mask,
                                                  self.xy2ij(seed),
                                                  scanRad,
                                                  ds9=ds9)
        measCtr = self.ij2xy(measCtr)
        cmd.respond('%sCentroid=%0.2f,%0.2f,%d,%d' % \
                    (self.name,
                     measCtr[0], measCtr[1],
                     nCounts, nPts))

        cmd.finish()

    doCentroid.helpText = ('centroid itime=S [window=X0,Y0,X1,Y1] [bin=N] [bin=X,Y] [on=X,Y]',
                                'centroid file=NAME [on=X,Y]')
    
    def guideLoopIsStopped(self):
        """ The guide loop is telling us that it can and should be reaped.

        When we are done, the guide loop cmd will has been finished and the
        guide loop destroyed.

        """

        self.guideLoop = None
        
    def doGuide(self, cmd):
        """ Start or stop guiding.

          - 
        """

        if cmd.argDict.has_key('off'):
            if self.guideLoop:
		self.guideLoop.stop()
                cmd.finish('%sTxt="Turning guiding off."' % (self.name))
            else:
                cmd.fail('%sTxt="Guiding is already off."' % (self.name))
            return

        elif cmd.argDict.has_key('tweak'):
            d = self.parseTweaks(cmd)
            if not self.guideLoop:
                cmd.fail('%sTxt="No guide loop to tweak."' % (self.name))
                return
            self.guideLoop.tweak(cmd, d)

        else:
            if self.guideLoop:
                cmd.fail('%sTxt="cannot start guiding while guiding"' % (self.name))
                return

            # Make a copy of our configuration for the loop to modify
            config = self.getActiveConfig()
        
            self.guideLoop = GuideLoop.GuideLoop(self, cmd, config.copy())
            self.guideLoop.run()

    def getActiveConfig(self):
        """ Return the current configuration dictionary. """

        if self.config == None:
            self.config = self.defaults.copy()

        return self.config
    
    def doZap(self, cmd):
        """ Try hard to cancel any existing exposure and remove any internal exposure state.

        Only the exposure owner or an APO user can zap an exposure.
        """
        
        # Only let the exposure owner or any APO user control an active exposure.
        #
        gCmd = self.guidingCmd

        if gCmd == None:
            cmd.fail('%sTxt="no guiding cmd to zap"' % (self.name))
            return
        
        if gCmd.program() != cmd.program() and cmd.program() != 'APO':
            cmd.fail('%sTxt="guiding belongs to %s.%s"' % (self.name,
                                                           gCmd.program(),
                                                           gCmd.username()))
            return


        self.camera.zap(cmd)
	if self.guideLoop:
	    self.guideLoop.abort(cmd)
	    self.guideLoop = None
        cmd.finish('')

    doZap.helpText = ('zap            - stop and active exposure and/or cleanup.')

    def doSetMask(self, cmd):
        """ Load a mask to apply.

        CmdArgs:
            a FITS filename, based from self.imBaseDir
        """

        if len(cmd.argv) == 1:
            fname = self.maskFile
        if len(cmd.argv) == 2:
            fname = cmd.argv[1]
        else:
            cmd.fail('%sTxt="usage: setMask [filename]"' % (self.name))
            return

        self._setMask(fname)
        
        cmd.finish('maskFile=%s' % (self.name, CPL.qstr(fname)))
        
    def doSetBoresight(self, cmd):
        """ Define the boresight

        CmdArgs:
            x,y  - unbinned pixels
        """

        if len(cmd.argv) != 3:
            cmd.fail('%sTxt="usage: setBoresight X Y"' % (self.name))
            return
        x = float(cmd.argv[1])
        y = float(cmd.argv[2])
        self.boresightPixel = [x,y]

        cmd.finish('%sBoresight=%0.1f,%0.1f' % (self.name, x, y))
                   
    def doSetScale(self, cmd):
        """ Define the global guiding gain

        CmdArgs:
            N  - guider gain
        """

        if len(cmd.argv) != 2:
            cmd.fail('%sTxt="usage: setScale N"' % (self.name))
            return
        x = float(cmd.argv[1])
        self.guideScale = x

        cmd.finish('%sScale=%0.2f' % (self.name, x))

    def doSetThresh(self, cmd):
        """ Handle setThresh command, which sets the stddev factor to consider a blob a star.

        CmdArgs:
           int    - the new 
        """

        parts = cmd.raw_cmd.split()
        if len(parts) != 2:
            cmd.fail('%sTxt="usage: setThresh value."')
            return

        try:
            t = float(parts[1])
        except:
            cmd.fail('%sTxt="setThresh value must be a number"')
            return

        self.starThresh = t
        cmd.finish('starThreshold=%0.2f' % (self.starThresh))
                   
    def doSet(self, cmd):
        """ Handle set command, which lets us override a certain amount of guiding state.

        CmdArgs:
           stateName=value
        """

	cmd.fail('txt="set command not yet implemented."')
                   
    def _doCmdExpose(self, cmd, type, ignoreArgs):
        """ Parse the exposure arguments and act on them.

        Args:
            cmd    - the controlling Command
            type   - 'object' or 'dark'
            ignoreArgs - a list of command arguments to ignore (UNUSED)
            
        CmdArgs:
            time   - exposure time, in seconds
            window - subframe, (X0,Y0,X1,Y1)
            bin    - binning, (N) or (X,Y)
            file   - a file name. If specified, the time,window,and bin arguments are ignored.
            
        Returns:
            - a filename
        """

        matched, notMatched, leftovers = cmd.match([('time', float),
                                                    ('window', str),
                                                    ('bin', str),
                                                    ('file', str)])

        if matched.has_key('file'):
            fname = self.findFile(cmd, matched['file'])
            if not fname:
                cmd.fail('%sTxt=%s' % (self.name,
                                       CPL.qstr("No such file: %s" % (matched['file']))))
                return

            return fname
        else:
            if not matched.has_key('time') :
                cmd.fail('%sTxt="Exposure commands must specify exposure times"' % (self.name))
                return
            time = matched['time']

            window = None
            bin = None
            if matched.has_key('bin'):
                bin = self.parseBin(matched['bin'])
            if matched.has_key('window'):
                window = self.parseWindow(matched['window'])

            return self._doExpose(cmd, type, time, bin, window)

    def _doExpose(self, cmd, type, itime, bin, window):
        """ Actually request an exposure from a camera.

        Args:
            cmd         - the controlling command
            type        - 'object' or 'dark'
            time        - integration time in seconds.
            bin         - X,Y pair of integers
            window      - X0,Y0,X1,Y1

        Returns:
             - filename of the resulting processed frame.

        """
        
        rawFrame = self.camera.expose(cmd, type, itime, window=window, bin=bin)
        finalFrame = self._consumeRawFrame(cmd, rawFrame)
        return finalFrame
    
    def findFile(self, cmd, fname):
        """ Get the absolute path for a given filename. Looks in the 'current directory' """
        
        return fname
    
    def _getBestCenter(self, cmd, fname):
        """ Return the best center for a given file, as defined by findstars()

        I __really__ want to filter the output of findstars, possibly re-ordering
        based on some desirability map and functions. Some of the guider fields have
        horrible aberrations...
        """

        if fname == None:
            fname = self._doCmdExpose(cmd, 'expose', 'centroid')
        fits = pyfits.open(fname)
        img = fits[0].data
        fits.close()
	isSat, stars = PyGuide.findStars(
            data = img
	)

        if isSat:
            cmd.warn('%sFindstarsSaturated=%s' % (self.name, CPL.qstr(fname)))
        if len(stars) == 0:
            return None
        else:
            return self.ij2xy(stars[0].center)
        
    def _doCentroid(self, cmd, seedPos, fname=None, scanRad=None):
        """ Takes a single guider exposure and centroids on the given position. This overrides but
        does not stop the guiding loop.
        """

        if fname == None:
            fname = self._doCmdExpose(cmd, 'expose', 'centroid')
        fits = pyfits.open(fname)
        img = fits[0].data
        fits.close()

        if scanRad == None:
            scanRad = self.scanRad

        cmd.warn('%sDebug=%s' % (self.name,
                                 CPL.qstr('centroid seed=%0.2f,%0.2f rad=%0.1f fsize=%d fname=%s' % \
                                          (seedPos[0], seedPos[1], scanRad,
                                           len(img), fname))))
        ds9 = cmd.argDict.get('ds9', False)
        centroid = PyGuide.centroid(img,
                                    self.mask,
                                    self.xy2ij(seedPos),
                                    scanRad,
                                    ds9=ds9)
        
        return centroid

    def _doStarShape(self, cmd, center, fname=None, predFWHM=2.0):
        """ Gets star shape information on a given object.
        """

        fits = pyfits.open(fname)
        img = fits[0].data

        try:
            shape = PyGuide.starShape(img,
                                      self.getMaskForFits(fits),
                                      center,
                                      predFWHM=predFWHM)
        finally:
            fits.close()
        
        return shape

    def getMaskForFits(self, fits):
        """ Generate a mask file matchng the given FITS file.
        """

        pass
        
    def getMask(self, bin):
        """ Return a numarray mask appropriate to the given binning.

        Args:
             bin      - the desired binning factor.

        Note that we use the opposite sign convention for mask files than numarray does.
        """

        return self.mask.getMaskForBinning(bin)
    
    def _setMask(self, fname):
	""" Set our mask to the contents of the given filename. """

	self.mask = GuiderMask.GuiderMask(fname)
        self.maskFile = fname
        
    def _consumeRawFrame(self, cmd, rawFrame):
        """ Turn a raw frame into a proper file for the rest of the guider code.

        This will likely need to be subclassed. By default, we do nothing.
        """

        return rawFrame
    
    def parseWindow(self, parts):
        """ Parse a window specification of the form X0,Y0,X1,Y1.

        Args:
           s    - a string of the form "X0,Y0,X1,Y1"

        Returns:
           - the window coordinates, as a 4-tuple of integers.

        Raises:
           Exception on parsing errors.
           
        """

        try:
            coords = map(int, parts)
            if len(coords) != 4:
                raise Exception
        except:
            raise Exception("window format must be X0,Y0,X1,Y1 with all coordinates being integers.")

        return coords

    def parseCoord(self, parts):
        """ Parse a coordinate pair of the form X,Y.

        Args:
           s    - a string of the form "X,Y"

        Returns:
           - the window coordinates, as a pair of integers.

        Raises:
           Exception on parsing errors.
           
        """

        try:
            coords = map(float, parts)
            if len(coords) != 2:
                raise Exception
        except:
            raise Exception("cooordinate format must be X,Y with all coordinates being floats (not %s)." % (s))

        return coords

    def parseBin(self, parts):
        """ Parse a binning specification of the form X,Y or N

        Args:
           s    - a string of the form "X,Y" or "N"

        Returns:
           - the binning factors coordinates, as a duple of integers.

        Raises:
           Exception on parsing errors.
           
        """

        try:
            if len(parts) == 1:
                parts = parts * 2
            if len(parts) != 2:
                raise Exception
            coords = map(int, parts)
        except:
            raise Exception("binning must be specified as X,Y or N with all coordinates being integers.")

        return coords
        
        
