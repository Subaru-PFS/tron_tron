#!/usr/bin/env python

__all__ = ['Guider']

""" The "guider" command.

Coordinate notes:
  - Because the TCC CONVERT command views the world in unbinned, full-frame coordinates (image/ccd centric),
    but the guide cameras can both bin and window, we need to be sure to convert to & from ccd- and frame- systems
    whenever we go betweem the cameras and the TCC.
"""

import os
import sys

import pyfits
import Command
import Actor
import CPL
import GuideLoop
import GuiderMask
import GuideFrame
import MyPyGuide

class Guider(Actor.Actor):
    """ The Guider class is expected to be subclassed for the specific guiders.
    """
    
    def __init__(self, camera, guiderName, **argv):
        """
        """
        
        Actor.Actor.__init__(self, guiderName, **argv)

        self.commands.update({'status':     self.statusCmd,
                              'expose':     self.exposeCmd,
                              'dark':       self.darkCmd,
                              'centroid':   self.centroidCmd,
                              'findstars':  self.findstarsCmd,
                              'init':       self.initCmd,
                              'set':        self.setCmd,
                              'setMask':    self.setMaskCmd,
                              'guide':      self.guideCmd,
                              'zap':        self.zapCmd
                              })

        self.camera = camera
        self.guideLoop = None
        self.mask = None
        self.exposureInfo = None
        
        self._setDefaults()
        self.config = self.defaults.copy()
        self._setMask(None, self.config['maskFile'])
    
    def _setDefaults(self):
        self.defaults = {}

        for name in ('bias',
                     'readNoise', 'ccdGain',
                     'ccdSize', 'binning',
                     'starThresh', 'radius',
                     'maskFile', 'imagePath',
                     'fitErrorScale'):
            self.defaults[name] = CPL.cfg.get(self.name, name)
        self.size = self.defaults['ccdSize']
        self.defaults['minOffset'] = CPL.cfg.get('telescope', 'minOffset')

    def statusCmd(self, cmd):
        """ Returns camera and guide loop status keywords. """

        self.camera.statusCmd(cmd, doFinish=False)
        self.mask.statusCmd(cmd, doFinish=False)
	
        if self.guideLoop:
            self.guideLoop.doStatus(cmd, doFinish=False)

        cmd.finish("guiding=%s" % (CPL.qstr(self.guideLoop != None)))
    statusCmd.helpText = ('status', 'returns many status keywords.')
    
    def exposeCmd(self, cmd):
        """ Take a single guider exposure and return it. This overrides but
        does not stop the guiding loop.
        """
        
        tweaks = self.parseCmdTweaks(cmd, self.config)

        def cb(cmd, fname, frame, tweaks=None):
            cmd.respond('camFile=%s' % (CPL.qstr(fname)))
            cmd.finish()
            
        self.doCmdExpose(cmd, cb, 'expose', tweaks)

    exposeCmd.helpText = ('expose itime=S [window=X0,Y0,X1,Y1] [bin=N] [bin=X,Y]', 
                          'take an open-shutter exposure')

    def darkCmd(self, cmd):
        """ Take a single guider dark and return it. This overrides but
        does not stop the guiding loop.
        """

        tweaks = self.parseCmdTweaks(cmd, self.config)

        def cb(cmd, fname, frame):
            cmd.respond('darkFile=%s' % (CPL.qstr(fname)))
            cmd.finish()
            
        self.doCmdExpose(cmd, cb, 'dark', tweaks)
        
    darkCmd.helpText = ('dark itime=S [window=X0,Y0,X1,Y1] [bin=N] [bin=X,Y]',
                        'take a closed-shutter exposure')

    def initCmd(self, cmd):
        """ Clean up/stop/initialize ourselves. """

        if self.guideLoop:
            self.guideLoop.stop()
            
        self.config = self.defaults.copy()
        
        # Optionally handle the command as a GImCtrl
        if cmd.program() == 'TC01':
            self.doTccInit(cmd)
            return
            
	cmd.finish('')
    initCmd.helpText = ('init', 're-initialize camera')
        
    def findstarsCmd(self, cmd):
        """ Takes a single guider exposure and runs findstars on it. This overrides but
        does not stop the guiding loop.
        """

        # Optionally handle the command as a GImCtrl
        if cmd.program() == 'TC01':
            return self.doTccFindstars(cmd)

        tweaks = self.parseCmdTweaks(cmd, self.config)
        
        # Get the image
        self.doCmdExpose(cmd, self._findstarsCB, 'expose', tweaks=tweaks)

    def _findstarsCB(self, cmd, filename, frame, tweaks=None):
        """ Callback called when an exposure is done.
        """
        
        cmd.respond('%sDebug=%s' % \
                    (self.name, CPL.qstr('checking filename=%s' % (filename))))

        self.genFilesKey(cmd, 'findstarsFiles', True, filename, None, None, None, filename)
        
        isSat, stars = MyPyGuide.findstars(cmd, filename, self.mask, frame, tweaks)
        if not stars:
            cmd.fail('txt="no stars found"')
            return

        MyPyGuide.genStarKeys(cmd, stars)
        cmd.finish()
        
    findstarsCmd.helpText = ('findstars itime=S [window=X0,Y0,X1,Y1] [bin=N] [bin=X,Y]')

    def centroidCmd(self, cmd):
        """ Takes a single guider exposure and runs findstars on it. This overrides but
        does not stop the guiding loop.
        """

        # Optionally handle the command as a GImCtrl
        if cmd.program() == 'TC01':
            return self.doTccCentroid(cmd)

        tweaks = self.parseCmdTweaks(cmd, self.config)
        
        # Get the image
        self.doCmdExpose(cmd, self._centroidCB, 'expose', tweaks=tweaks)

    def _centroidCB(self, cmd, filename, frame, tweaks=None):
        """ Callback called when an exposure is done.
        """
        
        cmd.respond('%sDebug=%s' % \
                    (self.name, CPL.qstr('checking filename=%s' % (filename))))

        if cmd.argDict.has_key('on'):
            seed = self.parseCoord(cmd.argDict['on'])
        else:
            isSat, stars = MyPyGuide.findstars(cmd, filename, self.mask,
                                               frame, tweaks,
                                               cnt=1)
            if not stars:
                cmd.fail('centroidTxt="no stars found"')
                return

            seed = stars[0].ctr
            
        # Currently unnecessary if we have run findstars, but that might change, so
        # always call the centroid routine.
        #
        star = MyPyGuide.centroid(cmd, filename, self.mask, frame, seed, tweaks)
        if not star:
            cmd.fail('centroidTxt="no star found"')
            return

        MyPyGuide.genStarKey(cmd, star, keyName='centroid')
        cmd.finish()
        
    centroidCmd.helpText = ('centroid itime=S [window=X0,Y0,X1,Y1] [bin=N] [bin=X,Y] [on=X,Y]',
                                'centroid file=NAME [on=X,Y]')
    
    def guideLoopIsStopped(self):
        """ The guide loop is telling us that it can and should be reaped.

        When we are done, the guide loop cmd will have been finished and the
        guide loop destroyed.

        """
        g = self.guideLoop
        self.guideLoop = None

        CPL.log("guideLoopIsStopped", "deleting %s" % (g))
        
        del g
        
    def guideCmd(self, cmd):
        """ Start or stop guiding.

          - 
        """

        if cmd.argDict.has_key('off'):
            if self.guideLoop:
                self.guideLoop.stop(cmd)
                cmd.finish('%sTxt="Turning guiding off."' % (self.name))
            else:
                cmd.fail('%sTxt="Guiding is already off."' % (self.name))
            return
        elif cmd.argDict.has_key('zap'):
            if self.guideLoop:
                self.guideLoop.stop(cmd)
                cmd.finish('%sTxt="Turning guiding off."' % (self.name))
                self.guideLoop.stopGuiding()
            else:
                cmd.fail('%sTxt="Guiding is already off."' % (self.name))
            return

        elif cmd.argDict.has_key('tweak'):
            if not self.guideLoop:
                cmd.fail('%sTxt="No guide loop to tweak."' % (self.name))
                return
            self.guideLoop.tweak(cmd)
            cmd.finish('')
        else:
            if self.guideLoop:
                cmd.fail('%sTxt="cannot start guiding while guiding"' % (self.name))
                return

            tweaks = self.parseCmdTweaks(cmd, self.config)
            
            self.guideLoop = GuideLoop.GuideLoop(self, cmd, tweaks)
            self.guideLoop.run()

    def zapCmd(self, cmd):
        """ Try hard to cancel any existing exposure and remove any internal exposure state.

        Only the exposure owner or an APO user can zap an exposure.
        """

        if not self.guideLoop:
            cmd.warn('%sTxt="no guiding loop to zap"' % (self.name))
        else:
            # Only let the exposure owner or any APO user control a guide loop.
            #
            gCmd = self.guideLoop.cmd
            
            if gCmd.program() != cmd.program() and cmd.program() != 'APO':
                cmd.fail('%sTxt="guiding loop belongs to %s.%s"' % (self.name,
                                                                    gCmd.program(),
                                                                    gCmd.username()))
                return

	    self.guideLoop.stop(cmd, doFinish=False)
	    self.guideLoop = None

        self.camera.zap(cmd)
        cmd.finish('')
    zapCmd.helpText = ('zap', 'stop and active exposure and/or cleanup.')

    def setMaskCmd(self, cmd):
        """ Load a mask to apply.

        CmdArgs:
            a FITS filename, based from self.imBaseDir
        """

        if len(cmd.argv) == 1:
            fname = self.defaults['maskFile']
        if len(cmd.argv) == 2:
            fname = cmd.argv[1]
        else:
            cmd.fail('%sTxt="usage: setMask [filename]"' % (self.name))
            return

        self._setMask(cmd, fname)
        
    setMaskCmd.helpText = ('setMask [filename]',
                           'load a mask file. Reload existing mask if no file is specified')
        
    def setCmd(self, cmd):
        """ Handle set command, which lets us override a certain amount of guiding state.

        CmdArgs:
           stateName=value
        """

        self.config = self.parseCmdTweaks(cmd, self.config)
	cmd.finish('')
                   
    def doCmdExpose(self, cmd, cb, type, tweaks):
        """ Parse the exposure arguments and act on them.

        Args:
            cmd    - the controlling Command
            cb     - a function which will be called as cb(cmd, filename, frame, tweaks)
            type   - 'object' or 'dark'
            tweaks - dictionary of configuration values.
            
        CmdArgs:
            time   - exposure time, in seconds
            window - subframe, (X0,Y0,X1,Y1)
            bin    - binning, (N) or (X,Y)
            file   - a file name. If specified, the time,window,and bin arguments are ignored.
            
        Returns:
            - a 
        """

        matched, notMatched, leftovers = cmd.match([('time', float),
                                                    ('window', str),
                                                    ('bin', str),
                                                    ('file', str)])

        if matched.has_key('file'):
            filename = self.findFile(cmd, matched['file'])
            if not filename:
                cmd.fail('%sTxt=%s' % (self.name,
                                       CPL.qstr("No such file: %s" % (matched['file']))))
                return

            frame = GuideFrame.ImageFrame(self.size)
            frame.setImageFromFITSFile(filename)
            
            cb(cmd, filename, frame, tweaks=tweaks)

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

            frame = GuideFrame.ImageFrame(self.size)
            frame.setImageFromWindow(bin, window)

            self.doCBExpose(cmd, cb, type, time, frame, cbArgs={'tweaks':tweaks}) 

    def doCBExpose(self, cmd, cb, type, itime, frame, cbArgs={}):
        """ Actually request an exposure from a camera.

        When the exposure is actually finished, the callback function
        will be invoked as:
           cb(cmd, filename, frame, **cbArgs)

        Args:
            cmd         - the controlling command
            cb          - the callback function
            type        - 'object' or 'dark'
            time        - integration time in seconds.
            frame       - requested ImageFrame
            cbArgs      - a dictionary of args to pass to the callback.

        Returns:
             - a callback object

        """

        def _cb(cmd, filename, frame):
            cmd.respond('camFile=%s'% (CPL.qstr(filename)))
            cb(cmd, filename, frame, **cbArgs)
            
        cmd.warn('debug=%s' % (CPL.qstr("exposing %s(%s) frame=%s" % (type, itime, frame))))
        
        mycb = self.camera.cbExpose(cmd, _cb, type, itime, frame)
        return mycb

    def findFile(self, cmd, fname):
        """ Get the absolute path for a given filename.

        Args:
            cmd    - the controlling Command
            fname  - a relative or absolute filename. If relative, use the
                     'current' directory.

        Returns:
            - an absolute filename.
        """
        
        return fname
    
    def _setMask(self, cmd, filename, doFinish=True):
	""" Set our mask to the contents of the given filename. """

        try:
            self.mask = GuiderMask.GuiderMask(cmd, filename)
        except Exception, e:
            if cmd:
                cmd.fail('could not set the mask file: %s')
            else:
                raise

        if cmd and doFinish:
            cmd.finish('maskFile=%s' % (CPL.qstr(filename)))
        
    def parseWindow(self, w):
        """ Parse a window specification of the form X0,Y0,X1,Y1.

        Args:
           s    - a string of the form "X0,Y0,X1,Y1"

        Returns:
           - the window coordinates, as a 4-tuple of integers.

        Raises:
           Exception on parsing errors.
           
        """

        try:
            parts = w.split(',')
            coords = map(int, parts)
            if len(coords) != 4:
                raise Exception
        except:
            raise Exception("window format must be X0,Y0,X1,Y1 with all coordinates being integers.")

        return coords

    def parseCoord(self, c):
        """ Parse a coordinate pair of the form X,Y.

        Args:
           s    - a string of the form "X,Y"

        Returns:
           - the window coordinates, as a pair of integers.

        Raises:
           Exception on parsing errors.
           
        """

        try:
            parts = c.split(',')
            coords = map(float, parts)
            if len(coords) != 2:
                raise Exception
        except:
            raise Exception("cooordinate format must be X,Y with all coordinates being floats (not %s)." % (parts))

        return coords

    def parseBin(self, s):
        """ Parse a binning specification of the form X,Y or N

        Args:
           s    - a string of the form "X,Y" or "N"

        Returns:
           - the binning factors coordinates, as a duple of integers.

        Raises:
           Exception on parsing errors.
           
        """

        try:
            parts = s.split(',')
            if len(parts) == 1:
                parts = parts * 2
            if len(parts) != 2:
                raise Exception
            coords = map(int, parts)
        except:
            raise Exception("binning must be specified as X,Y or N with all coordinates being integers.")

        return coords
        
        
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
    
    def parseCmdTweaks(self, cmd, baseConfig):
        """ Parse all configuration tweaks in a command, and modify a copy of baseConfig.
        """

        tweaks = baseConfig.copy()
        matched, unmatched, leftovers = cmd.match([('time', float),
                                                   ('bin', self.parseBin),
                                                   ('window', self.parseWindow),
                                                   ('radius', float),
                                                   ('thresh', float),
                                                   ('retry', int),
                                                   ('restart', str),
                                                   ('cnt', int)])

        tweaks.update(matched)

        return tweaks

    def getCurrentDir(self):
        """ Return the current image directory. """

        dateStr = CPL.getDayDirName()
        return os.path.join(self.config['imagePath'], dateStr)
        
    def genFilesKey(self, cmd, keyName, isNewFile,
                    finalname, maskname, camname, darkname, flatname):
        """ Generate an xxxFiles keyword.

        Args:
            cmd          - the controlling Command to respond to.
            keyName      - the name of the keyword.
            isNewFile    - whether  
            finalname, maskname, camname, darkname, flatname - the component filenames.

        If the files are in the current active directory, then output relative filenames.
        Otherwise output absolute filenames.
        """

        cd = self.getCurrentDir()

        files = []
        for f in finalname, maskname, camname, darkname, flatname:
            if f == None:
                files.append('')
            elif os.path.commonprefix(cd, f) == cd:
                files.append(f[len(cd)+1:])
            else:
                files.append(f)

        qfiles = map(CPL.qstr, files)
        cmd.respond("%s=%d,%s" % (keyName, int(isNewFile),
                                  qfiles.join(',')))
                             
