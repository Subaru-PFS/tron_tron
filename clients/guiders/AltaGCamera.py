__all__ = ['AltaGCamera']

import os.path

import client
import CPL
import GCamera
import AltaNet

class AltaGCamera(GCamera.GCamera):
    """ Use an Alta camera.

    Takes images and puts fleshed out versions into the given public directory.
    
    """
    
    def __init__(self, name, path, hostname, **argv):
        """ Use an Alta camera. """
        
        GCamera.GCamera.__init__(self, name, path, **argv)

        self.cam = AltaNet.AltaNet(hostName=hostname)

        # Track the name of the last file.
        self.lastRead = "unknown"

        # Track binning and window, since we don't want to have to set them for each exposure.
        self.binning = [None, None]
        self.window = [None, None, None, None]
    
    def zap(self, cmd):
        pass
    
    def status(self, cmd):
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
    
    def expose(self, cmd, expType, itime, window=None, bin=None):
        """ Take an exposure of the given length, optionally binned/windowed.

        Args:
            expType  - 'dark' or 'expose'
            itime    - seconds to integrate for
            window   ? optional window spec (X0, Y0, X1, Y1)
            bin      ? optional binning spec (X, Y)

        Returns:
            The full FITS path.
        """

        # Check format:
        if bin and bin != self.binning:
            self.cam.setBinning(*bin)
            self.binning = bin
        if window and window != self.window:
            self.cam.setWindow(*window)
            self.window = window

        doShutter = expType == 'expose'

        if doShutter:
            d = self.cam.expose(itime)
        else:
            d = self.cam.dark(itime)

        filename = self.writeFITS(cmd, d)

        # Try to recover image memory. 
        del d
        
        return filename


        
