__all__ = ['GimGCamera']

import shutil
import os.path

import client
import CPL
import GCamera
import GimCtrlConnection
import GuideFrame

class GimCtrlGCamera(GCamera.GCamera):
    """ Use a GImCtrl-controlled camera. """
    
    def __init__(self, name, inPath, outPath, ccdSize, **argv):
        """ Use a GImCtrl-controlled camera.

        Args:
           name    - user-level name of the camera system. Used to choose image
                     directory and filenames.
           inPath  - Where the GimCtrl system saves its files.
           outPath - Where our output files go.
           host, port - socket to reach the camera.
        """
        
        GCamera.GCamera.__init__(self, name, outPath, ccdSize, **argv)

        self.inPath = inPath

        self.conn = GimCtrlConnection.GimCtrlConnection(argv['host'],
                                                        argv['port'])

    def statusCmd(self, cmd, doFinish=True):
        """ Generate status keywords.

        Args:
           cmd       - the controlling Command
           doFinish  - whether or not to .finish the command
        """

        pass
    
    def zap(self, cmd):
        pass


    def rawCmd(self, cmd, timeout):
        """ Send a command directly to the controller. """

        cmdStr = cmd.raw_cmd

        # 
        if cmd.program() != "TC01":
            cmdStr.strip()
        cmd.warn("debug=%r" % (cmdStr))
        
        return self.conn.sendCmd(cmdStr, timeout)
        
    def genExposeCommand(self, cmd, expType, itime, frame):
        """ Generate the command line for a given exposure.

        Returns:
            actor
            commandline
        
        Args:
            expType  - 'dark' or 'expose'
            itime    - seconds to integrate for
            frame    - ImageFrame describing us.

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

        cmdParts.append("%d %d" % tuple(frame.frameBinning))
        cmdParts.append("%d %d %d %d" % tuple(frame.imgFrameAsCtrAndSize()))

        return None, ' '.join(cmdParts)

    def expose(self, cmd, expType, itime):
        """ Take an exposure of the given length, optionally binned/windowed.

        Args:
            expType  - 'dark' or 'expose'
            itime    - seconds to integrate for
            frame    - ImageFrame

        """

        # Build arguments
        actor, cmdLine = self.genExposeCommand(cmd, expType, itime, frame=frame)
        
        return self.rawCmd(cmdLine, itime + 15)

    def cbExpose(self, cmd, cb, expType, itime, frame):
        """ Take an exposure of the given length, optionally binned/windowed.

        Args:
            expType  - 'dark' or 'expose'
            itime    - seconds to integrate for
            frame    - ImageFrame

        """

        # Build arguments
        actor, cmdLine = self.genExposeCommand(cmd, expType, itime, frame=frame)

        def _cb(cmd, ret):
            filename = self.getLastImageName(cmd)
            frame = GuideFrame.ImageFrame(self.ccdSize)
            frame.setImageFromFITSFile(filename)
            cb(cmd, filename, frame)
            
        # Trigger exposure
        return self.conn.sendExposureCmd(cmd, cmdLine, itime, _cb)

    def getLastImageName(self, cmd):
        filename = self._getLastImageName()
        cmd.respond("%sRawImage=%s" % (self.name, CPL.qstr(filename)))

        return filename
        
    def _getLastImageName(self):
        """ Fetch the name of the last image read from the last.image name.
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
        os.chown(newPath, 0644)
        return newPath
    
        
