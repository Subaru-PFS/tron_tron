#!/usr/bin/env python

__all__ = ['Guider']

""" The "guider" command.

 For commands from the tcc, we need to support:
    init
    setcam N
    doread S Xbin Ybin Xctr Yctr Xsize Ysize
    findstars N Xctr Yctr Xsize Ysize XpredFWHM YpredFWHM
    
findstars            1      171.0      171.0     1024.0     1024.0        3.5        3.5
  yields:
i RawText="findstars            1      171.0      171.0     1024.0     1024.0        3.5        3.5"
i RawText="3 3   213.712 144.051   5.73 4.90 77.5   192.1 5569.1 328.0   0.008 0.008   0"
: RawText=" OK"

  but must be preceded by a doread:

doread       8.00     3     3      171.0      171.0     1024.0     1024.0
  
"""

import inspect
import os
import pprint
import sys
import time
import traceback

import PyGuide
import pyfits
import client
import Command
import Actor
import CPL
import RO
import GuideLoop

class Guider(Actor.Actor, GuideLoop.GuideLoop):
    """ The Guider class is expected to be subclassed for the specific guiders.
    """
    
    def __init__(self, camera, guiderName, **argv):
        Actor.Actor.__init__(self, guiderName, **argv)

        self.commands.update({'status':     self.doStatus,
                              'expose':     self.doExpose,
                              'dark':       self.doDark,
                              'centroid':   self.doCentroid,
                              'findstars':  self.doFindstars,
                              'init':       self.doInit,
                              'setMask':    self.doSetMask,
                              'setScale':   self.doSetScale,
                              'setBoresight': self.doSetBoresight,
                              'guide':      self.doGuide,
                              'dodark':     self.doTccDoread,
                              'doread':     self.doTccDoread,
                              'setcam':     self.doTccSetcam,
                              'test':       self.doTest,
                              'showstatus': self.doTccShowstatus,
                              'zap':        self.doZap
                              })

        self.camera = camera
        self.activeExposure = None
        self.guiding = False
        self.guidingCmd = None
        self.mask = None

        # the tcc sends 'findstars' after requesting an image. Keep the image name around.
        self.imgForTcc = None
        
    def xy2ij(self, pos):
        return pos[1], pos[0]

    def ij2xy(self, pos):
        return pos[1], pos[0]

    def echoToTcc(self, cmd, ret):
        """ If cmd comes from the TCC, pass the ret lines back to it. """

        if cmd.program() == 'TC01':
            for i in range(len(ret)-1):
                cmd.respond('txtForTcc=%s' % (CPL.qstr(ret[i])))
            cmd.finish('txtForTcc=%s' % (CPL.qstr(ret[-1])))
        else:
            for i in range(len(ret)-1):
                cmd.respond('rawTxt=%s' % (CPL.qstr(ret[i])))
            cmd.finish('rawTxt=%s' % (CPL.qstr(ret[-1])))
            
    def doInit(self, cmd):
        """ Clean up/stop/initialize ourselves. """

        # Optionally handle the command as a GImCtrl
        #
        if cmd.program() == 'TC01':
            cmd.respond('txtForTcc="init"')
            cmd.finish('txtForTcc="OK"')
            return
        else:
            cmd.finish()
        
    def doTccShowstatus(self, cmd):
        """ Respond to a tcc 'showstatus' command.
        
showstatus
1 "PXL1024" 1024 1024 16 -26.02 2 "camera: ID# name sizeXY bits/pixel temp lastFileNum"
1 1 0 0 0 0 nan 0 nan "image: binXY begXY sizeXY expTime camID temp"
8.00 1000 params: boxSize (FWHM units) maxFileNum
 OK

        """
        
        cmd.respond('txtForTcc=%s' % (CPL.qstr(cmd.raw_cmd)))
        cmd.respond("txtForTcc=%s" % (CPL.qstr('%d "%s" %d %d %d %0.2f nan "%s"' % \
                                            (self.GImCamID, self.GImName,
                                             self.size[0], self.size[1], 16,
                                             self.camera.cam.read_TempCCD(),
                                             "camera: ID# name sizeXY bits/pixel temp lastFileNum"))))
        cmd.respond('txtForTcc=%s' % (CPL.qstr('%d %d %d %d %d %d nan 0 nan "%s"' % \
                                            (1, 1, 0, 0, 0, 0,
                                             "image: binXY begXY sizeXY expTime camID temp"))))
        cmd.respond('txtForTcc=%s' % (CPL.qstr('8.00 1000 "%s"' % \
                                            ("params: boxSize (FWHM units) maxFileNum"))))
        cmd.finish('txtForTcc=" OK"')
    
    def doTccSetcam(self, cmd):
        """ Respond to a tcc 'setcam N' command.

        This is intended to follow an 'init' command, and truly configures a GImCtrl camera. We, however,
        do not need it, so we gin up a fake response.

        A sample response for the NA2 camera is:
        setcam 1
        1 \"PXL1024\" 1024 1024 16 -11.11 244 \"camera: ID# name sizeXY bits/pixel temp lastFileNum\"
         OK
        """

        # Parse off the camera number:
        id = int(cmd.argv[-1])
        self.GImCamID = id
        
        # lastImageNum = self.cam.lastImageNum()
        lastImageNum = 'nan'   # self.cam.lastImageNum()
        
        cmd.respond('txtForTcc=%s' % (CPL.qstr(cmd.raw_cmd)))
        cmd.respond('txtForTcc=%s' % (CPL.qstr('%d "%s" %d %d %d nan %s "%s"' % \
                                            (id, self.GImName,
                                             self.size[0], self.size[1], 16,
                                             lastImageNum,
                                             "camera: ID# name sizeXY bits/pixel temp lastFileNum"))))
        cmd.finish('txtForTcc=" OK"')

    def doTccDoread(self, cmd):
        """ Respond to a tcc 'doread' cmd.

        The response to the command:
           doread       1.00     3     3      171.0      171.0     1024.0     1024.0
        is something like:
           doread       1.00     3     3      171.0      171.0     1024.0     1024.0
           3 3 0 0 341 341 1.00 8 -10.99 \"image: binXY begXY sizeXY expTime camID temp\"
            OK
        
        """

        # Parse the tcc command. It will _always_ have all fields
        #
        try:
            type, iTime, xBin, yBin, xCtr, yCtr, xSize, ySize = cmd.raw_cmd.split()
        except:
            cmd.fail('txtForTcc=%s' % (CPL.qstr("Could not parse command %s" % (cmd.raw_cmd))))
            return

        try:
            if type == 'dodark':
                type = 'dark'
            else:
                type = 'expose'
                
            iTime = float(iTime)
            xBin = int(xBin); yBin = int(yBin)
            xCtr = float(xCtr); yCtr = float(yCtr)
            xSize = float(xSize); ySize = float(ySize)

            # Some realignments, since the TCC can request funny things.
            if xSize == 0:
                xSize = self.size[0] / xBin
            if ySize == 0:
                ySize = self.size[1] / yBin

            bin = [xBin, yBin]
            window = [int(xCtr - (xSize/2)),
                      int(yCtr - (ySize/2)),
                      int(xCtr + (xSize/2) + 0.5),
                      int(yCtr + (ySize/2) + 0.5)]
        except:
            cmd.fail('txtForTcc=%s' % (CPL.qstr("Could not interpret command %s" % (cmd.raw_cmd))))
            return

        try:
            exp = self._doExpose(cmd, type, iTime, bin, window)
        except Exception, e:
            raise
            cmd.fail('txtForTcc=%s' % (CPL.qstr('Could not take an exposure: %s' % (e))))
            return

        # cmd.respond('imgFile=%s' % (CPL.qstr(exp)))

        # Keep some info around for findstars
        #
        self.imgForTcc = exp
        self.binForTcc = xBin, yBin
        
        ccdTemp = self.camera.cam.read_TempCCD()
        cmd.respond('txtForTcc=%s' % (CPL.qstr(cmd.raw_cmd)))
        cmd.respond('txtForTcc=%s' % (CPL.qstr('%d %d %d %d %d %d %0.2f %d %0.2f %s' % \
                                            (bin[0], bin[1],
                                             window[0], window[1], window[2], window[3],
                                             iTime, self.GImCamID, ccdTemp,
                                             "image: binXY begXY sizeXY expTime camID temp"))))
        cmd.finish('txtForTcc=" OK"')

    def trimUnit(self, x, size):
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
    
    def doTccFindstars(self, cmd):
        """ Pretends to be a GImCtrl running 'findstars'

        findstars            1      171.0      171.0     1024.0     1024.0        3.5        3.5
            yields:
        findstars            1      171.0      171.0     1024.0     1024.0        3.5        3.5
        3 3   213.712 144.051   5.73 4.90 77.5   192.1 5569.1 328.0   0.008 0.008   0
        OK
        """

        fname = self.imgForTcc
        cmd.respond('%sDebug=%s' % (self.name, CPL.qstr('checking filename=%s' % (fname))))
        fits = pyfits.open(fname)
        img = fits[0].data
        fits.close()
        
        # Parse out what (little) we need: the number of stars and the predicted size.
        #
        try:
            name, cnt, x0, y0, xSize, ySize, xPredFWHM, yPredFWHM = cmd.raw_cmd.split()
        except ValueError, e:
            cmd.fail('gcamTxt="findstars must take all tcc arguments"')
            return

        cnt = int(cnt)
        x0, y0, xSize, ySize, xPredFWHM, yPredFWHM = map(float, (x0, y0, xSize, ySize, xPredFWHM, yPredFWHM))
        if xSize == 0.0: xSize = self.size[0]
        if ySize == 0.0: ySize = self.size[1]
        
        # Build a mask from:
        #   self.mask
        #   the given window
        mask = self.getMask(bin=self.binForTcc, optImg=img)
        if mask != None:
            mask = self.maskOutFromPosAndSize(mask.copy(), x0, y0, xSize, ySize, excludeRect=True)
        else:
            cmd.warn('%sTxt="no mask available"')
        
        try:
            isSat, stars = PyGuide.findStars(
		img, mask,
                self.bias, self.rdNoise, self.ccdGain,
                dataCut = self.starThresh,
                verbosity=0
                )
        except Exception, e:
            cmd.warn('debug=%s' % (CPL.qstr(e)))
            raise
            isSat = False
            stars = []

        if isSat:
            cmd.warn('findstarsSaturated=%s' % (self.name, CPL.qstr(fname)))
        cmd.respond('findstarsCnt=%d' % (len(stars)))

        cmd.respond('txtForTcc=%s' % (CPL.qstr(cmd.raw_cmd)))

        scale = self.binForTcc[0]

        if len(stars) == 0:
            cmd.respond('txtForTcc="no stars found"')
        else:
            i=1
            for star in stars:
                ctr = self.ij2xy(star.ctr)

                try:
                    shape = PyGuide.starShape(img,
                                              mask,
                                              star.ctr)
                    fwhm = shape.fwhm
                    chiSq = shape.chiSq
                    bkgnd = shape.bkgnd
                    ampl = shape.ampl
                except:
                    fwhm = 0.0        # nan does not work.
                    chiSq = 0.0
                    bkgnd = 0.0
                    ampl = 0.0
                    
                cmd.respond('findstar=%d,%0.3f,%0.3f, %0.3f,%0.3f,%0.3f, %0.3f,%0.3f,%0.3f, %0.1f,%0.1f,%0.1f' % \
                            (i, ctr[0], ctr[1],
                             star.err[1], star.err[1], star.asymm,
                             fwhm, fwhm, chiSq,
                             star.counts, bkgnd, ampl))
                             
                cmd.respond('txtForTcc=%s' % \
                            (CPL.qstr("%d %d %0.3f %0.3f %0.3f %0.3f 0.0 0.0 %10.1f 0.0 %0.2f %0.2f 0" % \
                                      (self.binForTcc[0], self.binForTcc[1],
                                       ctr[0], ctr[1],
                                       fwhm, fwhm,
                                       star.counts,
                                       star.err[1], star.err[0]))))
                i += 1
                if i >= cnt:
                    break
            
        cmd.finish('txtForTcc=" OK"')

    def doStatus(self, cmd):
        self.camera.status(cmd)

        if self.mask:
            maskFile = self.mask
        else:
            maskFile = ''
        cmd.finish('maskFile=%s' % (CPL.qstr(maskFile)))
    
    def doTest(self, cmd):
        cmd.finish('txtForTcc=" OK"')

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
	isSat, sd = PyGuide.findStars(
		data = img,
                mask=self.mask,
                ds9=ds9
	)

        if isSat:
            cmd.warn('%sFindstarsSaturated=%s' % (self.name, CPL.qstr(fname)))

        cmd.respond('%sFindstarsCnt=%d' % (self.name, len(sd)))
        i=1
        for counts, ctr, rad, totPts in sd:
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

        fname = self._doCmdExpose(cmd, 'expose', 'centroid')

        if not cmd.argDict.has_key('on'):
            seed = self._getBestCenter(cmd, fname)
            if seed == None:
                cmd.fail('%sTxt="no stars found"' % (self.name))
                return
        else:
            seed = self.parseCoord(cmd.argDict['on'])
            

        centroid = self._doCentroid(cmd, seed, fname)
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
    
    def doGuide(self, cmd):
        """ Start or stop guiding.

          - 
        """

        if cmd.argDict.has_key('off'):
            if self.guiding:
                self.guiding = False
                cmd.finish('%sTxt="Turning guiding off."' % (self.name))
            else:
                cmd.fail('%sTxt="Guiding is already off."' % (self.name))
                
            return

        
        if self.guidingCmd:
            cmd.fail('%sTxt="cannot start guiding while guiding"' % (self.name))
            return

        self._doGuide(cmd)

    def failGuiding(self, why):
        """ Stop guiding, 'cuz something went wrong.
        """

        self.guidingCmd.respond('%sGuiding=False' % (self.name))
        self.guidingCmd.fail('%sTxt=%s' % (self.name, CPL.qstr(why)))
        self.guiding=False
        self.guidingCmd=None
        return

    def stopGuiding(self):
        """ Stop guiding, on purpose
        """

        self.guidingCmd.finish('%sGuiding=False' % (self.name))
        self.guiding=False
        self.guidingCmd=None
        return
        
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
        self.failGuiding('Zapped guide command')
        cmd.finish('')

    doZap.helpText = ('zap            - stop and active exposure and/or cleanup.')

    def _doCmdExpose(self, cmd, type, ignoreArgs):
        """ Parse the exposure arguments and act on them.

        Args:

        CmdArgs:
            time   - exposure time, in seconds
            window - subframe, (X0,Y0,X1,Y1)
            bin    - binning, (N) or (X,Y)
            file   - a file name. If specified, the time,window,and bin arguments are ignored.
            
        Keys:
        
        Returns:
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
        rawFrame = self.camera.expose(cmd, type, itime, window=window, bin=bin)
        finalFrame = self._consumeRawFrame(cmd, rawFrame)
        return finalFrame

    
    def findFile(self, cmd, fname):
        return fname
    
    def _getBestCenter(self, cmd, fname):
        """ Return the best center for a given file, as defined by findstars() """

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

    def getMask(self, bin=[1,1], img=None, optImg=None):
        """ Return a numarray mask appropriate to the given binning.

        Args:
             bin      - the desired binning factor.
             img      - an image to base the mask on. Overrides any builtin mask.
             optImg   - an image file to use if no builtin mask (or img= file) is available.

        Note that we use the opposite sign convention for mask files than numarray does.
        """

        # First, override everything with img if specified.
        if img:
            mask = img <= 0
        else:
            mask = self.mask

        # Next, use optImg if no other mask is available.
        if mask == None and optImg != None:
            mask = optImg <= 0
            
        return mask
    
    def doClearMask(self, cmd):
        """ Stop using any mask. """

        self.mask = None
        cmd.finish('%sMask=None')

    def XXdoSetMask(self, cmd):
        """ Load a mask to apply.

        CmdArgs:
            a FITS filename, based from self.imBaseDir
        """

        if len(cmd.argv) != 2:
            cmd.fail('%sTxt="usage: setMask FILENAME"' % (self.name))
            return
        fname = cmd.argv[-1]

        f = pyfits.open(fname)
        im = f[0].data
        f.close()
        
        self.mask = im
        cmd.finish('%sMask=%s' % (self.name, CPL.qstr(fname)))
        

    def _setMask(self, fname):
        f = pyfits.open(fname)
        im = f[0].data
        f.close()
        
        self.mask = im <= 0

    def doSetMask(self, cmd):
        """ Load a mask to apply.

        CmdArgs:
            a FITS filename, based from self.imBaseDir
        """

        if len(cmd.argv) == 2:
            fname = cmd.argv[1]
        else:
            cmd.fail('%sTxt="usage: setMask filename"' % (self.name))
            return

        self._setMask(fname)
        
        cmd.finish('%sMask=%s' % (self.name, CPL.qstr(fname)))
        
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
        
    def returnKeys(self, cmd, inst):
        """ Generate all the keys describing our next file. """
        
        pass
        
