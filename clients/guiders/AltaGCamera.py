__all__ = ['AltaGCamera']

import os.path

import client
import CPL
import GCamBase
import AltaNet
import GuideFrame

class AltaGCamera(GCamBase.GCamBase):
    """ Use an Alta camera.

    Takes images and puts fleshed out versions into the given public directory.
    
    """
    
    def __init__(self, name, path, hostname, ccdSize, **argv):
        """ Use an Alta camera. """
        
        GCamBase.GCamBase.__init__(self, name, path, ccdSize, **argv)

        self.cam = AltaNet.AltaNet(hostName=hostname)

        # Track binning and window, since we don't want to have to set them for each exposure.
        self.frame = None
        self.binning = [None, None]
        self.window = [None, None, None, None]
    
    def zap(self, cmd):
        pass
    
    def statusCmd(self, cmd, doFinish=True):
        """ Generate status keywords. Does NOT finish teh command.
        """

        coolerStatus = self.cam.coolerStatus()
        if self.lastImage == None:
            fileStatus = 'lastImage='
        else:
            fileStatus = 'lastImage="%s"' % (self.lastImage)
            
        cmd.respond("%s; %s" % (coolerStatus, fileStatus))

    def coolerStatus(self, cmd, doFinish=True):
        """ Generate status keywords. Does NOT finish teh command.
        """

        coolerStatus = self.cam.coolerStatus()
        cmd.respond(coolerStatus)

        if doFinish:
            cmd.finish()

    def setTemp(self, cmd, temp, doFinish=True):
        """ Adjust the cooling loop.

        Args:
           cmd  - the controlling command.
           temp - the new setpoint, or None if the loop should be turned off. """

        self.cam.setCooler(temp)
        self.coolerStatus(cmd, doFinish=doFinish)
        
    def setFan(self, cmd, level, doFinish=True):
        """ Adjust the cooling fan level

        Args:
           cmd   - the controlling command.
           level - the new fan level. 0..3
        """

        self.cam.setFan(level)
        self.coolerStatus(cmd, doFinish=doFinish)
        
    def getCCDTemp(self):
        """ Return the current CCD temperature. """

        return self.cam.read_TempCCD()
    
    def cbExpose(self, cmd, cb, expType, itime, frame, cbArgs={}, errorsTo=None):
        """ Take an exposure of the given length, optionally binned/windowed.

        Args:
            expType  - 'dark' or 'expose'
            itime    - seconds to integrate for
            frame    - ImageFrame

        """

        try:
            filename = self.expose(cmd, expType, itime, frame)
            frame = GuideFrame.ImageFrame(self.ccdSize)
            frame.setImageFromFITSFile(filename)
            cb(cmd, filename, frame, **cbArgs)
        except Exception, e:
            if errorsTo:
                errorsTo(cmd, e)
            else:
                raise
        
    def expose(self, cmd, expType, itime, frame):
        """ Take an exposure of the given length, optionally binned/windowed.

        Args:
            expType  - 'dark' or 'expose'
            itime    - seconds to integrate for
            frame    - ImageFrame

        Returns:
            The full FITS path.
        """

        #cmd.warn('debug=%s' % (CPL.qstr("alta expose %s %s secs, frame=%s" \
        #                                % (expType, itime, frame))))
        
        # Check format:
        bin = frame.frameBinning
        window = list(frame.imgFrameAsWindow())
        #window[2] -= 1
        #window[3] -= 1

        if bin != self.binning:
            self.cam.setBinning(*bin)
            self.binning = bin
        if window != self.window:
            self.cam.setWindow(*window)
            self.window = window

        self.frame = frame
            
        doShutter = expType == 'expose'

        if doShutter:
            d = self.cam.expose(itime)
        else:
            d = self.cam.dark(itime)

        filename = self.writeFITS(cmd, frame, d)
        
        # Try hard to recover image memory. 
        del d
        
        return filename


        
