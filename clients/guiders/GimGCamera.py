__all__ = ['GimGCamera']

import os.path

import client
import CPL
import GCamera

class GimGCamera(GCamera.GCamera):
    """ Use a GImCtrl-controlled camera.

    Takes GIm images, either directly from the controller or via the TCC, and puts fleshed
    out versions into the given public directory.
    
    """
    
    def __init__(self, name, camName, inPath, outPath, viaTCC, **argv):
        """ Use a GImCtrl-controlled camera. Depending on the viaTCC, call the camera directly
            or command it via the TCC.
            """
        
        GCamera.GCamera.__init__(self, name, camName, outPath, **argv)

        self.inPath = inPath
        self.viaTCC = viaTCC

        # Track the name of the last file.
        self.lastRead = "unknown"


    def zap(self, cmd):
        pass
    
    def genExposeCommand(self, cmd, expType, itime, window=None, bin=None, callback=None):
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
        if self.viaTCC:
            cmdParts.append('gcam')
            
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

        cid = "%s.%s" % (cmd.fullname, self.name)
        if self.viaTCC:
            return 'tcc', ' '.join(cmdParts)
        else:
            return self.name, ' '.join(cmdParts)

    def expose(self, cmd, expType, itime, window=None, bin=None, callback=None):
        """ Take an exposure of the given length, optionally binned/windowed.

        Args:
            expType  - 'dark' or 'expose'
            itime    - seconds to integrate for
            window   ? optional window spec (X0, Y0, X1, Y1)
            bin      ? optional binning spec (X, Y)

        """

        # Build arguments
        actor, cmdLine = self.genExposeCommand(cmd, expType, itime, window=window, bin=bin)
        
        cid = self.cidForCmd(cmd)
        if callback:
            ret = client.callback(actor, cmdLine,
                                  callback=callback, cid=cid)
        else:
            ret = client.call(actor, cmdLine, cid=cid)
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
    
        
        
