""" The minimum required to emulate the TCC's GImCtrl API. """

__all__ = ['TCCGcam']

import sys

import CPL
import GuideFrame
import MyPyGuide

class TCCGcam(object):
    '''
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
  
    '''
    
    def __init__(self, **argv):
        sys.stderr.write("in __init__\n")
        
        self.commands.update({'dodark':     self.doTccDoread,
                              'doread':     self.doTccDoread,
                              'setcam':     self.doTccSetcam,
                              'OK':       self.doOK,
                              'showstatus': self.doTccShowstatus})

        # the tcc sends 'findstars' after requesting an image. Keep the image name around.
        self.fileForTcc = None

    def echoToTcc(self, cmd, ret):
        """ If cmd comes from the TCC, pass the ret lines back to it. """

        for i in range(len(ret)-1):
            cmd.respond('txtForTcc=%s' % (CPL.qstr(ret[i])))

        cmd.finish('txtForTcc=%s' % (CPL.qstr(ret[-1])))
            
    def doOK(self, cmd):
        """ A TOTAL hack, for recovering after we fail in the middle of a TCC command. This
        merely generates a fake completion for the TCC. Even though we say OK, the command 
        has certainly failed, and the TCC will recognize this -- because it has not 
        seen the expected command response. 
        """
        
        cmd.finish('txtForTcc=" OK"')

    def doTccInit(self, cmd):
        """ Clean up/stop/initialize ourselves. """

        cmd.respond('txtForTcc="init"')
        cmd.finish('txtForTcc="OK"')
        
    def doTccShowstatus(self, cmd):
        ''' Respond to a tcc 'showstatus' command.
        
showstatus
1 "PXL1024" 1024 1024 16 -26.02 2 "camera: ID# name sizeXY bits/pixel temp lastFileNum"
1 1 0 0 0 0 nan 0 nan "image: binXY begXY sizeXY expTime camID temp"
8.00 1000 params: boxSize (FWHM units) maxFileNum
 OK

        '''
        temp = 0.0    # self.camera.cam.read_TempCCD(),
        cmd.respond('txtForTcc=%s' % (CPL.qstr(cmd.raw_cmd)))
        cmd.respond("txtForTcc=%s" % (CPL.qstr('%d "%s" %d %d %d %0.2f nan "%s"' % \
                                            (self.GImCamID, self.GImName,
                                             self.size[0], self.size[1], 16,
                                             temp,
                                             "camera: ID# name sizeXY bits/pixel temp lastFileNum"))))
        cmd.respond('txtForTcc=%s' % (CPL.qstr('%d %d %d %d %d %d nan 0 nan "%s"' % \
                                            (1, 1, 0, 0, 0, 0,
                                             "image: binXY begXY sizeXY expTime camID temp"))))
        cmd.respond('txtForTcc=%s' % (CPL.qstr('8.00 1000 "%s"' % \
                                            ("params: boxSize (FWHM units) maxFileNum"))))
        cmd.finish('txtForTcc=" OK"')
    
    def doTccSetcam(self, cmd):
        ''' Respond to a tcc 'setcam N' command.

        This is intended to follow an 'init' command, and truly configures a GImCtrl camera. We, however,
        do not need it, so we gin up a fake response.

        A sample response for the NA2 camera is:
        setcam 1
        1 \"PXL1024\" 1024 1024 16 -11.11 244 \"camera: ID# name sizeXY bits/pixel temp lastFileNum\"
         OK
        '''

        # Parse off the camera number:
        gid = int(cmd.argv[-1])
        self.GImCamID = gid
        
        lastImageNum = 'nan' # self.camera.lastImageNum() # 'nan'
        
        cmd.respond('txtForTcc=%s' % (CPL.qstr(cmd.raw_cmd)))
        cmd.respond('txtForTcc=%s' % (CPL.qstr('%d "%s" %d %d %d nan %s "%s"' % \
                                            (gid, self.GImName,
                                             self.size[0], self.size[1], 16,
                                             lastImageNum,
                                             "camera: ID# name sizeXY bits/pixel temp lastFileNum"))))
        cmd.finish('txtForTcc=" OK"')

    def doTccDoread(self, cmd):
        ''' Respond to a tcc 'doread' cmd.

        The response to the command:
           doread       1.00     3     3      171.0      171.0     1024.0     1024.0
        is something like:
           doread       1.00     3     3      171.0      171.0     1024.0     1024.0
           3 3 0 0 341 341 1.00 8 -10.99 \"image: binXY begXY sizeXY expTime camID temp\"
            OK
        
        '''

        # Cancel out any record of older exposures.
        self.frameForTcc = None
        self.imgForTcc = None

        # Parse the tcc command. It will _always_ have all fields
        #
        try:
            type, itime, xBin, yBin, xCtr, yCtr, xSize, ySize = cmd.raw_cmd.split()
        except:
            cmd.fail('txtForTcc=%s' % (CPL.qstr("Could not parse command %s" % (cmd.raw_cmd))))
            return

        try:
            if type == 'dodark':
                type = 'dark'
            else:
                type = 'expose'
                
            itime = float(itime)
            xBin = int(xBin); yBin = int(yBin)
            xCtr = float(xCtr); yCtr = float(yCtr)
            xSize = float(xSize); ySize = float(ySize)

            # Some realignments, since the TCC can request funny things.
            xMax = self.size[0] / xBin
            yMax = self.size[1] / yBin
            if xSize <= 0 or xSize > xMax:
                xSize = xMax
            if ySize <= 0 or ySize > yMax:
                ySize = xMax
            
            bin = [xBin, yBin]
            window = [int(xCtr - (xSize/2)),
                      int(yCtr - (ySize/2)),
                      int(xCtr + (xSize/2) + 0.5),
                      int(yCtr + (ySize/2) + 0.5)]

            if window[0] < 0: window[0] = 0
            if window[1] < 0: window[1] = 0
            if window[2] > xMax: window[2] = xMax
            if window[3] > yMax: window[3] = yMax

        except:
            cmd.fail('txtForTcc=%s' % (CPL.qstr("Could not interpret command %s" % (cmd.raw_cmd))))
            return

        frame = GuideFrame.ImageFrame(self.size)
        frame.setImageFromWindow(bin, window)
        
        cmd.respond('txtForTcc=%s' % (CPL.qstr(cmd.raw_cmd)))
        self.doCBExpose(cmd, self._doTccDoreadCB,
                        type, itime, frame,
                        cbArgs={'itime':itime})


    def _doTccDoreadCB(self, cmd, filename, frame, itime=0,
                       warning=None, failure=None):


        if warning:
            cmd.warn('text=%s' % (CPL.qstr(warning)))
            
        if failure:
            cmd.warn('text=%s' % (CPL.qstr(failure)))
            cmd.warn('txtForTcc=%s' % (CPL.qstr(failure)))
            cmd.finish('txtForTcc=" OK"')
            return

        # Keep some info around for findstars
        #
        self.frameForTcc = frame
        self.fileForTcc = filename
        
        ctr, size = frame.imgFrameAsCtrAndSize()
        ccdTemp = 0.0   # self.camera.cam.read_TempCCD()
        cmd.respond('txtForTcc=%s' % (CPL.qstr('%d %d %d %d %d %d %0.2f %d %0.2f %s' % \
                                            (frame.frameBinning[0], frame.frameBinning[1],
                                             ctr[0], ctr[1],
                                             size[0], size[1],
                                             itime, self.GImCamID, ccdTemp,
                                             "image: binXY begXY sizeXY expTime camID temp"))))
        cmd.finish('txtForTcc=" OK"')
        
    def doTccFindstars(self, cmd):
        ''' Pretends to be a GImCtrl running 'findstars'

        findstars            1      171.0      171.0     1024.0     1024.0        3.5        3.5
            yields:
        findstars            1      171.0      171.0     1024.0     1024.0        3.5        3.5
        3 3   213.712 144.051   5.73 4.90 77.5   192.1 5569.1 328.0   0.008 0.008   0
        OK
        '''

        cmd.respond('txtForTcc=%s' % (CPL.qstr(cmd.raw_cmd)))
        cmd.respond('%sDebug=%s' % (self.name, CPL.qstr('checking filename=%s' % (self.fileForTcc))))

        if not self.fileForTcc or not self.frameForTcc:
            cmd.warn('error="No doread image available for TCC findstars!"')
            cmd.finish('txtForTcc=" OK"')
            return
            
        # Parse out what we need: the number of stars and the predicted size.
        #
        try:
            name, cnt, x0, y0, xSize, ySize, xPredFWHM, yPredFWHM = \
                  cmd.raw_cmd.split()
        except ValueError, e:
            cmd.fail('gcamTxt="findstars must take all tcc arguments"')
            return

        cnt = int(cnt)
        x0, y0, xSize, ySize, xPredFWHM, yPredFWHM = \
            map(float, (x0, y0, xSize, ySize, xPredFWHM, yPredFWHM))
        if xSize == 0.0:
            xSize = self.size[0]
            x0 = 0
        if ySize == 0.0:
            ySize = self.size[1]
            y0 = 0

        doreadFrame = self.frameForTcc
        binning = doreadFrame.frameBinning

        # Build a frame for the findstars arguments, which we later use to
        # thin the accepted stars.
        #
        findstarsFrame = GuideFrame.ImageFrame(self.size)
        findstarsFrame.setImageFromCtrAndSize((binning[0], binning[1]),
                                              (x0, y0),
                                              (xSize, ySize))

        #cmd.warn('debug="tccDoread frame = %s"' % (doreadFrame))
        #cmd.warn('debug="tccFindstars frame = %s"' % (findstarsFrame))
        
        #maskFile, maskbits = self.mask.getMaskForFrame(cmd, self.fileForTcc, self.frameForTcc)
        #CPL.log('TCCGcam', 'note maskFile = %s' % (maskFile))
        
        tweaks = self.config
        parts = self.processCamFile(cmd, self.fileForTcc,
                                    tweaks, self.frameForTcc)
        procFile = parts[0]
        try:
            stars = MyPyGuide.findstars(cmd, procFile,
                                        self.frameForTcc, tweaks)
        except Exception, e:
            stars = []
            cmd.warn('debug=%s' % (CPL.qstr("pyquide.findstars failed with %s" % (e))))
            
        i = 0
        for s in stars:

            # Ignore stars outside the specified findstars frame....
            p = s.ctr[0] - findstarsFrame.frameOffset[0], s.ctr[1] - findstarsFrame.frameOffset[1],
            if not findstarsFrame.imgXYinFrame(p):
                CPL.log("TCCGcam", "out of frame. pos=%0.1f,%0.1f, p=%0.1f,%0.1f, frame=%s" % \
                        (s.ctr[0], s.ctr[1],
                         p[0], p[1], 
                         findstarsFrame))
                continue

            cmd.respond('txtForTcc=%s' % \
                        (CPL.qstr("%d %d %0.3f %0.3f %0.3f %0.3f 0.0 0.0 %10.1f 0.0 %0.2f %0.2f 0" % \
                                  (binning[0], binning[1],
                                   s.ctr[0], s.ctr[1],
                                   s.fwhm[0], s.fwhm[1],
                                   s.counts,
                                   s.err[0], s.err[1]))))
            i += 1
            if i >= cnt:
                break
            
        if i == 0:
            cmd.respond('txtForTcc="no stars found"')

        cmd.finish('txtForTcc=" OK"')

if __name__ == "__main__":
    import sys
    sys.stdout.write("in main\n")
