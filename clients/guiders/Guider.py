#!/usr/bin/env python

__all__ = ['Guider']

""" The "guider" command.

Coordinate notes:
  - Because the TCC CONVERT command views the world in unbinned, full-frame coordinates (image/ccd centric),
    but the guide cameras can both bin and window, we need to be sure to convert to & from ccd- and frame- systems
    whenever we go betweem the cameras and the TCC.
"""

import gc
import math
import os
import sys
import time
import pprint
import inspect

import numarray
import pyfits

import Command
import Actor
import CPL
import GuideLoop
import GuiderMask
import GuideFrame
import GuiderPath
import MyPyGuide
import client

class Guider(Actor.Actor):
    """ The Guider class is expected to be subclassed for the specific guiders.
    """
    
    def __init__(self, camera, guiderName, **argv):
        """
        """
        
        os.environ['TZ'] = 'UTC'
        time.tzset()
        
        Actor.Actor.__init__(self, guiderName, **argv)

        self.commands.update({'status':     self.statusCmd,
                              'doread':     self.exposeCmd,
                              'dodark':     self.darkCmd,
                              'expose':     self.exposeCmd,
                              'dark':       self.darkCmd,
                              'centroid':   self.centroidCmd,
                              'findstars':  self.findstarsCmd,
                              'init':       self.initCmd,
                              'set':        self.setCmd,
                              'setMask':    self.setMaskCmd,
                              'guide':      self.guideCmd,
                              'zap':        self.zapCmd,
                              })

        self.camera = camera
        self.guideLoop = None
        self.exposing = False
        self.mask = None
        self.exposureInfo = None
        self.darks = {}
        
        self._setDefaults()
        self.config = self.defaults.copy()
        self._setMask(None, self.config['maskFile'])
        self.pathControl = GuiderPath.GuiderPath(os.path.join(self.config['imageRoot'],
                                                              self.config['imageDir']),
                                                 self.name[0])
        self.ubufIDs = {}
        
    def realXxxCmd(self, cmd):
        self.xxxCmd(cmd, doFinish=True)
        
    def xxxCmd(self, cmd, place=None, doFinish=False):
        
        gc.collect()
        bufs = self.xxx(cmd)
        cmd.warn('ubufsCnt=%d; place=%s' % (len(bufs), place))
        if doFinish:
            cmd.finish()
        
    def xxx(self, cmd):
        ubufs = gc.get_referrers(numarray.numarraycore._UBuffer)
        return ubufs
    
        #refs = gc.get_referents(self)
        #for x in refs:
        #    CPL.log("refs", "Guide ref: %s" % (pprint.pformat(x)))
        #    for y in gc.get_referents(x):
        #        CPL.log("refs", "++++++++++ ref: %s" % (pprint.pformat(y)))
        
    def _setDefaults(self):
        self.defaults = {}

        for name in ('bias',
                     'readNoise', 'ccdGain',
                     'ccdSize', 'binning',
                     'thresh', 'cradius', 'radMult',
                     'retry', 'restart',
                     'maskFile', 'biasFile',
                     'imageHost', 'imageRoot', 'imageDir',
                     'fitErrorScale', 'doFlatfield',
                     'requiredInst', 'requiredPort',
                     'imCtrName', 'imScaleName'):
            self.defaults[name] = CPL.cfg.get(self.name, name)
        self.size = self.defaults['ccdSize']
        self.defaults['minOffset'] = CPL.cfg.get('telescope', 'minOffset')

    def genPGStatusKeys(self, cmd):
        """ Generate the default PyGuide status keys. """
        
        cmd.respond("fsDefThresh=%0.1f; fsDefRadMult=%0.1f" % (self.config['thresh'],
                                                               self.config['radMult']))
        cmd.respond("centDefRadius=%0.1f" % (self.config['cradius']))
        cmd.respond("fsActThresh=%0.1f; fsActRadMult=%0.1f" % (self.config['thresh'],
                                                               self.config['radMult']))
        cmd.respond("centActRadius=%0.1f" % (self.config['cradius']))
        cmd.respond('imageRoot=%s,%s' % (CPL.qstr(self.config['imageHost']),
                                         CPL.qstr(self.config['imageRoot'])))
        binning = self.config['binning']
        cmd.respond('defBinning=%d,%d' % (binning[0], binning[1]))
        
    def statusCmd(self, cmd, doFinish=True):
        """ Returns camera and guide loop status keywords. """

        # self.camera.statusCmd(cmd, doFinish=False)
        self.mask.statusCmd(cmd, doFinish=False)

        self.genPGStatusKeys(cmd)
	
        if self.guideLoop:
            self.guideLoop.statusCmd(cmd, doFinish=False)
        else:
            cmd.respond('guideState="off",""')
            
        if doFinish:
            cmd.finish()
                    
    statusCmd.helpText = ('status', 'returns many status keywords.')
    
    def exposeCmd(self, cmd):
        """ Take a single guider exposure and return it. This overrides but
        does not stop the guiding loop.
        """
        
        tweaks = self.parseCmdTweaks(cmd, self.config)

        def cb(cmd, fname, frame, tweaks=None, warning=None, failure=None):
            if warning:
                cmd.warn('text=%s' % (CPL.qstr(warning)))
            if failure:
                cmd.fail('text=%s' % (CPL.qstr(failure)))
            cmd.finish()
            
        self.doCmdExpose(cmd, cb, 'expose', tweaks)

    exposeCmd.helpText = ('expose time=S [window=X0,Y0,X1,Y1] [bin=N] [bin=X,Y]', 
                          'take an open-shutter exposure')

    def darkCmd(self, cmd):
        """ Take a single guider dark and return it. This overrides but
        does not stop the guiding loop.
        """

        tweaks = self.parseCmdTweaks(cmd, self.config)

        def cb(cmd, fname, frame, tweaks=None):
            cmd.finish()
            
        self.doCmdExpose(cmd, cb, 'dark', tweaks)
        
    darkCmd.helpText = ('dark time=S [window=X0,Y0,X1,Y1] [bin=N] [bin=X,Y]',
                        'take a closed-shutter exposure')

    def initCmd(self, cmd):
        """ Clean up/stop/initialize ourselves. """

        if self.guideLoop:
            self.guideLoop.stop(cmd)
            
        self.config = self.defaults.copy()
        
        # Optionally handle the command as a GImCtrl
        if cmd.program() == 'TC01':
            self.doTccInit(cmd)
            return

        self.camera.initCmd(cmd, doFinish=False)
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
        
        # Get the image and call the real findstars routine.
        self.doCmdExpose(cmd, self._findstarsCB, 'expose', tweaks=tweaks)

    def _findstarsCB(self, cmd, camFile, frame, tweaks=None, warning=None, failure=None):
        """ Callback called when an exposure is done.
        """

        if warning:
            cmd.warn('text=%s' % (CPL.qstr(warning)))
            
        if failure:
            cmd.fail('text=%s' % (CPL.qstr(failure)))
            return
            
        #cmd.warn('debug=%s' % \
        #         (CPL.qstr('findstars checking filename=%s with frame=%s' % (camFile, frame))))

        procFile, maskFile, darkFile, flatFile = self.processCamFile(cmd, camFile,
                                                                     tweaks)
        self.genFilesKey(cmd, 'f', tweaks['newFile'],
                         procFile, maskFile, camFile, darkFile, flatFile)
        cmd.respond("fsActThresh=%0.1f; fsActRadMult=%0.1f" % (tweaks['thresh'],
                                                               tweaks['radMult']))
        
        stars = MyPyGuide.findstars(cmd, procFile, maskFile, frame, tweaks)
        if not stars:
            cmd.fail('text="no stars found"')
            return

        try:
            cnt = int(cmd.argDict['cnt'])
        except:
            cnt = None
        
        MyPyGuide.genStarKeys(cmd, stars, caller='f', cnt=cnt)
        cmd.finish()
        
    findstarsCmd.helpText = ('findstars time=S [window=X0,Y0,X1,Y1] [bin=N] [bin=X,Y]')

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

    def _centroidCB(self, cmd, camFile, frame, tweaks=None, warning=None, failure=None):
        """ Callback called when an exposure is done.
        """
        
        if warning:
            cmd.warn('text=%s' % (CPL.qstr(warning)))
            
        if failure:
            cmd.fail('text=%s' % (CPL.qstr(failure)))
            return
            
        # cmd.respond('debug=%s' % (CPL.qstr('checking filename=%s' % (camFile))))

        procFile, maskFile, darkFile, flatFile = self.processCamFile(cmd, camFile,
                                                                     tweaks)
        cmd.respond("centActRadius=%0.1f" % (tweaks['cradius']))
        self.genFilesKey(cmd, 'c', tweaks['newFile'],
                         procFile, maskFile, camFile, darkFile, flatFile)
        
        if cmd.argDict.has_key('on'):
            seed = self.parseCoord(cmd.argDict['on'])
        else:
            stars = MyPyGuide.findstars(cmd, camFile, maskFile,
                                        frame, tweaks,
                                               cnt=1)
            if not stars:
                cmd.fail('text="no stars found"')
                return

            seed = stars[0].ctr
            
        # Currently unnecessary if we have run findstars, but that might change, so
        # always call the centroid routine.
        #
        star = MyPyGuide.centroid(cmd, camFile, maskFile, frame, seed, tweaks)
        if not star:
            cmd.fail('text="no star found"')
            return

        MyPyGuide.genStarKey(cmd, star, caller='c')
        cmd.finish()
        
    centroidCmd.helpText = ('centroid time=S [window=X0,Y0,X1,Y1] [bin=N] [bin=X,Y] [on=X,Y]',
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
                cmd.finish('text="Turning guiding off."')
            else:
                cmd.fail('text="Guiding is already off."')
            return
        elif cmd.argDict.has_key('zap'):
            if self.guideLoop:
                self.guideLoop.stop(cmd)
                cmd.finish('text="Forcing guiding off."')
                self.guideLoop.stopGuiding()
            else:
                cmd.fail('text="Guiding is already off."')
            return

        elif cmd.argDict.has_key('tweak'):
            if not self.guideLoop:
                cmd.fail('text="No guide loop to tweak."')
                return
            newTweaks = self.parseCmdTweaks(cmd, None)
            self.guideLoop.tweakCmd(cmd, newTweaks)
            cmd.finish('')
        elif cmd.argDict.has_key('on'):
            if self.guideLoop:
                # Hack, hack, double evil nasty hack: this is
                # here 'cuz I stupidly implemented centering offsets as
                # mini guide loops.
                if cmd.argDict.has_key('centerOn') and self.guideLoop.guidingType == 'manual':
                    newTweaks = self.parseCmdTweaks(cmd, None)
                    self.guideLoop.centerUp(cmd, newTweaks)
                else:
                    cmd.fail('text="cannot start guiding while guiding"')
                return

            tweaks = self.parseCmdTweaks(cmd, self.config)
            
            self.guideLoop = GuideLoop.GuideLoop(self, cmd, tweaks)
            self.guideLoop.run()
        else:
            cmd.fail('text="unknown guide command"')
            
    def zapCmd(self, cmd):
        """ Try hard to cancel any existing exposure and remove any internal exposure state.

        Only the exposure owner or an APO user can zap an exposure.
        """

        if not self.guideLoop:
            cmd.warn('text="no guiding loop to zap"')
        else:
            # Only let the exposure owner or any APO user control a guide loop.
            #
            gCmd = self.guideLoop.cmd
            
            if gCmd.program() != cmd.program() and cmd.program() != 'APO':
                cmd.fail('text="guiding loop belongs to %s.%s"' % (gCmd.program(),
                                                                   gCmd.username()))
                return

	    self.guideLoop.stop(cmd, doFinish=False)
	    self.guideLoop = None

        # self.camera.zap(cmd)
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
            cmd.fail('text="usage: setMask [filename]"')
            return

        self._setMask(cmd, fname)
        
    setMaskCmd.helpText = ('setMask [filename]',
                           'load a mask file. Reload existing mask if no file is specified')
        
    def setCmd(self, cmd):
        """ Handle set command, which lets us override a certain amount of guiding state.

        CmdArgs:
           stateName=value
        """

        kwBase = (self.config['cradius'], self.config['radMult'], self.config['thresh'])
        self.config = self.parseCmdTweaks(cmd, self.config)
        kwNew = (self.config['cradius'], self.config['radMult'], self.config['thresh'])

        if kwBase != kwNew:
            self.genPGStatusKeys(cmd)
            
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

        matched, notMatched, leftovers = cmd.match([('time', float), ('exptime', float),
                                                    ('window', str),
                                                    ('bin', str),
                                                    ('file', cmd.qstr)])

        #if notMatched:
        #    cmd.warn('text="unknown arguments: %s"' % (notMatched))
            
        if matched.has_key('exptime'):
            matched['time'] = matched['exptime']

        if matched.get('itime'):
            tweaks['itime'] = matched['time']

        # Extra double hack: have a configuration override to the filenames. And
        # if that does not work, look for a command option override.
        tweaks['newFile'] = True
        filename = None
        if matched.has_key('file'):
            filename = matched['file']
            tweaks['newFile'] = False
        forcefile = self.config.get('forceFile', None)
        if not filename and forcefile:
            cmd.warn('text=%s' % (CPL.qstr("using forceFile: %s" % (forcefile))))
            filename = forcefile
        
        if filename:
            imgFile = self.findFile(cmd, filename)

            if not imgFile:
                cmd.fail('text=%s' % (CPL.qstr("No such file: %s" % (filename))))
                return

            frame = GuideFrame.ImageFrame(self.size)
            frame.setImageFromFITSFile(imgFile)

            def _cb(cmd, filename, frame, warning=None, failure=None):
                if type == 'expose':
                    cmd.respond('camFile=%s'% (CPL.qstr(filename)))
                else:
                    cmd.respond('darkFile=%s'% (CPL.qstr(filename)))
                cb(cmd, filename, frame, tweaks=tweaks, warning=warning, failure=failure)
                
            self.camera.cbFakefile(cmd, _cb, imgFile)
            return
        
        else:
            if not matched.has_key('time') :
                cmd.fail('text="Exposure commands must specify exposure times"')
                return
            time = matched['time']

            window = None
            bin = None
            if matched.has_key('bin'):
                bin = self.parseBin(matched['bin'])
            if matched.has_key('window'):
                window = self.parseWindow(matched['window'])

            bin = tweaks.get('bin', window)
            window = tweaks.get('window', window)
            
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
o            cb          - the callback function
            type        - 'object' or 'dark'
            time        - integration time in seconds.
            frame       - requested ImageFrame
            cbArgs      - a dictionary of args to pass to the callback.

        Returns:
             - a callback object

        """

        if self.exposing:
            cmd.fail('text="exposure in progress"')
            return
        
        def _cb(cmd, filename, frame, warning=None, failure=None):
            self.exposing = False
            self.pathControl.unlock(cmd, filename)
            if type == 'expose':
                cmd.respond('camFile=%s'% (CPL.qstr(filename)))
            else:
                cmd.respond('darkFile=%s'% (CPL.qstr(filename)))
            cb(cmd, filename, frame, warning=warning, failure=failure, **cbArgs)
            
        CPL.log('Guider', 'exposing %s(%s) frame=%s' % (type, itime, frame))

        filename = self.pathControl.lockNextFilename(cmd)
        self.exposing = True
        mycb = self.camera.cbExpose(cmd, _cb, type, itime, frame, filename)
        return mycb

    def processCamFile(self, cmd, camFile, tweaks, frame=None):
        """ Given a raw cameraFile, optionally dark-subtract or flat-field.

        Args:
             cmd         - the controlling Command
             camFile     - a raw file from a camera.
             tweaks      - our configuration
             frame       ? an ImageFrame describing the camFile

        Returns:
             - the processed filename (possibly just camFile)
             - the matching maskFile
             - the dark file used (or None)
             - the flat file used (or None)

        Currently only generates the proper mask file. Flat-fielding and dark-subtracting
        are both unimplemented.
        """

        #t0 = time.time()
        if not frame:
            frame = GuideFrame.ImageFrame(self.size)
            frame.setImageFromFITSFile(camFile)

        maskFile, maskBits = self.mask.getMaskForFrame(cmd, camFile, frame)

        darkFile = self.getDarkForCamFile(camFile, tweaks)
            
        if tweaks.get('doFlatfield'):
            flatFile = maskFile
        else:
            flatFile = None

        procFile = camFile
        if flatFile:
            camFITS = pyfits.open(camFile)
            camBits = camFITS[0].data
            camBits = camBits * 1.0
            
            if darkFile:
                darkFITS = pyfits.open(darkFile)
                darkBits = darkFITS[0].data
                darkFITS.close()

                x0, y0, x1, y1 = frame.imgFrameAsWindow(inclusive=False)

                darkBits = darkBits[y0:y1, x0:x1]
                #cmd.warn('debug="dark shape=%s; img shape=%s"' % (darkBits.getshape(),
                #                                                  camBits.getshape()))
            else:
                darkBits = camBits * 0.0 + tweaks['bias']

            try:
                camBits -= darkBits
                camBits *= maskBits

                # Shove bias-level pixels into the mask so that displays look OK.
                # maskBits = maskBits > 0.01
                
                # Add a pedestal back in.
                # We could tell the PyGuide routines that the bias is 0, too.
                bias = tweaks['bias'] + math.sqrt(tweaks['readNoise'])
                camBits += bias

                # If necessary, squeeze pixels back into 16-bit unsigned values.
                min = camBits.min()
                max = camBits.max()

                CPL.log('processCamFile', "min=%01.f max=%0.1f step=%0.1f" % (min, max, bias))
                if min < 0:
                    camBits += -min
                    max += -min
                    min = 0

                if max > 65536:
                    camBits -= min
                    camBits *= ((65535 - min) / max)
                    camBits += min
                    
                    cmd.warn('debug="limits=%0.1f,%0.1f; newLimits=%01.f,%0.1f"' % \
                             (min, max,
                              camBits.min(), camBits.max()))

                #camBits = camBits.astype('u2')
                procFile = self.changeFileBase(camFile, "proc")
            except Exception, e:
                cmd.warn('text="flatfielding failed: %s"' % (e))
                         
            try:
                os.remove(procFile)
            except:
                pass

            
            camFITS[0].data = camBits
            camFITS.writeto(procFile)
            camFITS.close()

            del darkBits
            del camBits
            
        #t1 = time.time()
        #cmd.warn('debug="procFiles took %0.1fs"' % (t1-t0))
        
        del maskBits

        darkFile = None
        return procFile, maskFile, darkFile, flatFile
    
    def changeFileBase(self, filename, newbase):
        """ Replace the 'name' part of the filename with some other prefix.

        E.g. 'g0123.fits' -> 'mask0123.fits'

        """
        

        basedir, basefile = os.path.split(filename)
        numIdx = 0
        for i in range(len(basefile)):
            if basefile[i].isdigit():
                numIdx = i
                break
        basefile = newbase + basefile[numIdx:]
        return os.path.join(basedir, basefile)

            
    def getDarkForCamFile(self, camFile, tweaks):
        """ Return a dark file corresponding to the given camFile.

        Args:
            camFile:    a FITS file with all the required cards.

        Returns:
            - the full pathname of a dark file, or None if something went wrong.
        """

        if tweaks.get('doAutoDark'):
            camFITS = pyfits.open(camFile)
            h = camFITS[0].header
            camFITS.close()

            expTime = h['EXPTIME']
            if self.darks[expTime]:
                darkFile = self.darks[expTime]
            else:
                darkFile = None
        elif tweaks.get('biasFile'):
            return tweaks['biasFile']
        else:
            darkFile = None

        if not darkFile:
            return None
        
        frame = GuideFrame.ImageFrame(self.size)
        frame.setImageFromFITSFile(camFile)
        
    def findFile(self, cmd, fname):
        """ Get the absolute path for a given filename.

        Args:
            cmd    - the controlling Command
            fname  - a relative or absolute filename. If relative, use the
                     'current' directory.

        Returns:
            - an absolute filename, or None if no readable file found.
        """

        # Take an absolute path straight.
        if os.path.isabs(fname):
            if os.access(fname, os.R_OK):
                return fname
            return None

        # Otherwise try to find the file in our "current" directory.
        root, dir = self.getCurrentDirParts()

        path = os.path.join(root, dir, fname)
        if os.access(path, os.R_OK):
            return path

        path = os.path.join(root, fname)
        if os.access(path, os.R_OK):
            return path

        cmd.warn('text=%s' % (CPL.qstr("could not find file %s" % (path))))
        return None
        

    def _setMask(self, cmd, filename, doFinish=True):
	""" Set our mask to the contents of the given filename. """

        try:
            self.mask = GuiderMask.GuiderMask(cmd, filename, self.name)
        except Exception, e:
            if cmd:
                cmd.fail('could not set the mask file: %s')
            else:
                raise

        if cmd:
            self.mask.statusCmd(cmd, doFinish=doFinish)
        
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

    def parseSize(self, s):
        try:
            parts = s.split(',')
            if len(parts) != 2:
                raise Exception
            coords = map(int, parts)
        except:
            raise Exception("size must be specified as X,Y with both coordinates being integers.")

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
        
    def parseCmdTweaks(self, cmd, baseConfig):
        """ Parse all configuration tweaks in a command, and modify a copy of baseConfig.
        """

        if baseConfig:
            tweaks = baseConfig.copy()
        else:
            tweaks = {}
            
        matched, unmatched, leftovers = cmd.match([('time', float), ('exptime', float),
                                                   ('bin', self.parseBin),
                                                   ('window', self.parseWindow),
                                                   ('bias', float),
                                                   ('readNoise', float),
                                                   ('ccdGain', float),
                                                   ('cradius', float),
                                                   ('thresh', float),
                                                   ('radMult', float),
                                                   ('retry', int),
                                                   ('restart', cmd.qstr),
                                                   ('forceFile', cmd.qstr),
                                                   ('cnt', int),
                                                   ('doFlatfield', int),
                                                   ('autoSubframe', self.parseSize),
                                                   ('centerOn', self.parseCoord),
                                                   ('manDelay', float),
                                                   ('ds9', cmd.qstr)])

        #if leftovers:
        #    cmd.warn('text="unknown arguments: %s"' % (leftovers))
            
        if matched.has_key('exptime'):
            matched['time'] = matched['exptime']

        tweaks.update(matched)

        if matched.has_key('forceFile') and not matched['forceFile']:
            del tweaks['forceFile']

        # Punch a hole through to the given X display.
        ds9 = tweaks.get('ds9', False)
        if ds9:
            os.environ['DISPLAY'] = ds9
        else:
            if os.environ.get('DISPLAY'):
                del os.environ['DISPLAY']
                
        return tweaks

    def getCurrentDirParts(self):
        """ Return the two parts of the current image directory.

        Returns:
           - the essentially fixed imageRoot (e.g. '/export/images/')
           - the rest of the directory.
        """

        dateStr = CPL.getDayDirName()
        return self.config['imageRoot'], \
               os.path.join(self.config['imageDir'], dateStr)

    def getCurrentDir(self):
        """ Return the current image directory. """

        return os.path.join(*self.getCurrentDirParts())
        
    def genFilesKey(self, cmd, caller, isNewFile,
                    finalname, maskname, camname, darkname, flatname):
        """ Generate an xxxFiles keyword.

        Args:
            cmd          - the controlling Command to respond to.
            caller       - a string indicating whose files these are.
            isNewFile    - whether  
            finalname, maskname, camname, darkname, flatname - the component filenames.
        
        If the files are in the current active directory, then output relative filenames.
        Otherwise output absolute filenames.
        """

        root, dir = self.getCurrentDirParts()

        # Figure out the directory all the files are in
        dirs = []
        files = []
        for f in finalname, maskname, camname, darkname, flatname:
            if f == None:
                f = ''
            d, f = os.path.split(f)
            common = os.path.commonprefix([root, d])
            d = d[len(common):]
            dirs.append(d)
            files.append(f)

        d0 = ''
        useFullPaths = False
        for d in dirs:
            if d == '':
                continue
            if d0 == '':
                d0 = d
            else:
                if d != d0:
                    cmd.warn('text="guider images are not all in the same directory"')
                    useFullPaths = True
                    break

        # Some of the path directories differ. So put the directories into the filenames.
        if useFullPaths:
            d0 = ''
            for i in range(len(files)):
                files[i] = os.path.join(dirs[i], files[i])
        else:
            if len(d0) > 0 and d0[-1] != '/':
                d0 = d0 + '/'
        
        qfiles = map(CPL.qstr, files)
        cmd.respond("files=%s,%d,%s,%s" % (CPL.qstr(caller),
                                           int(isNewFile),
                                           CPL.qstr(d0),
                                           ','.join(qfiles)))
                             
