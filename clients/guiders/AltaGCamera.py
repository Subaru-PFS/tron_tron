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
        cmd.respond(coolerStatus)

    def setTemp(self, cmd, temp):
        """ Adjust the cooling loop.

        Args:
           cmd  - the controlling command.
           temp - the new setpoint, or None if the loop should be turned off. """

        self.cam.setCooler(temp)
        coolerStatus = self.cam.coolerStatus()
        cmd.finish(coolerStatus)
    
    def expose(self, cmd, expType, itime, window=None, bin=None, callback=None):
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

        cid = self.cidForCmd(cmd)

        doShutter = expType == 'expose'
        filepath = self._getFilename()

        if doShutter:
            self.cam.expose(itime, filepath)
        else:
            self.cam.dark(itime, filepath)
            

        return filepath

        
