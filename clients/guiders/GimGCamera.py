__all__ = ['GimGCamera']

import shutil
import os.path

import client
import CPL
import GCamera
import GimCtrlConnection

class GimGCamera(GCamera.GCamera):
    """ Use a GImCtrl-controlled camera. """
    
    def __init__(self, name, inPath, outPath, **argv):
        """ Use a GImCtrl-controlled camera.

        Args:
           name    - user-level name of the camera system. Used to choose image
                     directory and filenames.
           inPath  - Where the GimCtrl system saves its files.
           outPath - Where our output files go.
           host, port - socket to reach the camera.
        """
        
        GCamera.GCamera.__init__(self, name, outPath, **argv)

        self.inPath = inPath

        self.conn = GimCtrlConnection.GimCtrlConnection(argv['host'],
                                                        argv['port'])

    def zap(self, cmd):
        pass


    def rawCmd(self, cmd, timeout):
        """ Send a command directly to the controller. """

        return self.conn.sendCmd(cmd.raw_cmd, timeout)
        
    def genExposeCommand(self, cmd, expType, itime, window=None, bin=None):
        """ Generate the command line for a given exposure.

        Returns:
            actor
            commandline
        
        Args:
            expType  - 'dark' or 'expose'
            itime    - seconds to integrate for
            window   ? optional window spec (X0, Y0, X1, Y1)
            bin      ? optional binning spec (X, Y)

        """

        # Build arguments
        cmdParts = []
        if expType == 'dark':
            cmdParts.append("dodark")
        elif expType == 'expose':
            cmdParts.append("doread")
        else:
            raise RuntimeError("unknown exposure type: %s" % (expType))

        cmdParts.append("%0.2f" % (itime))

        if bin != None:
            cmdParts.append("/BinFactor=(%d,%d)" % (bin[0], bin[1]))
        if window != None:
            cmdParts.append("/Center=(%0.1f,%0.1f) /Size=(%0.1f,%0.1f)" % \
                            ((window[0] + window[2]) / 2,
                             (window[1] + window[3]) / 2,
                             (window[2] - window[0]),
                             (window[3] - window[1])))

        return None, ' '.join(cmdParts)

    def expose(self, cmd, expType, itime, window=None, bin=None):
        """ Take an exposure of the given length, optionally binned/windowed.

        Args:
            expType  - 'dark' or 'expose'
            itime    - seconds to integrate for
            window   ? optional window spec (X0, Y0, X1, Y1)
            bin      ? optional binning spec (X, Y)

        """

        # Build arguments
        actor, cmdLine = self.genExposeCommand(cmd, expType, itime, window=window, bin=bin)

        ret = self.rawCmd(cmdLine, itime + 15)
        self.echoToTcc(cmd, ret)

        return self.getLastImageName(cmd)
        
    def getLastImageName(self, cmd):
        filename = self._getLastImageName()
        cmd.respond("%sRawImage=%s" % (self.name, CPL.qstr(filename)))

        return filename
        
    def _getLastImageName(self):
        """ Fetch the name of the last image read from the last.image name.

        Squawk if the name has not changed.
        """
        
        f = open(os.path.join(self.inPath, "last.image"), "r")
        l = f.read()
        f.close()

        return os.path.join(self.inPath, l)
    
    def copyinNewRawImage(self):
        """ Copy (and annotate) the latest raw GimCtrl image into the new directory."""
        
        oldPath = self._getLastImageName()
        newPath = self._getFilename()

        # This is probably where we would annotate the image header.
        #
        shutil.copyfile(oldPath, newPath)
        return newPath
        
        
