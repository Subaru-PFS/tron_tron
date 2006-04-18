__all__ = ['GimCtrlGCamera']

import shutil
import os.path

import pyfits
import client
import CPL
import GCamBase
import GimCtrlConnection
import GuideFrame

class GimCtrlGCamBase(GCamBase.GCamBase):
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
        
        GCamBase.GCamBase.__init__(self, name, outPath, ccdSize, **argv)

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

        ctr, size = frame.imgFrameAsCtrAndSize()
        cmdParts.append("%0.2f %0.2f %0.2f %0.2f" % (ctr[0], ctr[1],
                                                     size[0], size[1]))

        return None, ' '.join(cmdParts)

    def cbExpose(self, cmd, cb, expType, itime, frame, errorsTo=None):
        """ Take an exposure of the given length, optionally binned/windowed.

        Args:
            expType  - 'dark' or 'expose'
            itime    - seconds to integrate for
            frame    - ImageFrame

        """

        # Build arguments
        actor, cmdLine = self.genExposeCommand(cmd, expType, itime, frame=frame)

        def _cb(cmd, ret):
            try:
                filename = self.copyinNewRawImage()
                frame = GuideFrame.ImageFrame(self.ccdSize)
                frame.setImageFromFITSFile(filename)
                cb(cmd, filename, frame)
            except Exception, e:
                if errorsTo:
                    errorsTo(cmd, e)
                else:
                    raise
            
        # Trigger exposure
        cmd.warn('debug=%s' % (CPL.qstr("exposure command: %s" % (cmdLine))))
        return self.conn.sendExposureCmd(cmd, cmdLine, itime, _cb)

