#!/usr/bin/env python

__all__ = ['GImCtrlActor']

import os.path
import pyfits

import client
import Actor
import CPL
import GCamera
import GimCtrlConnection
import GuideFrame

class GImCtrlActor(GCamera.GCamera, Actor.Actor):
    """ Use an Alta camera.

    Takes images and puts fleshed out versions into the given public directory.
    
    """
    
    def __init__(self, name, **argv):
        """ Use an Alta camera. """
        
        Actor.Actor.__init__(self, name, **argv)
        GCamera.GCamera.__init__(self, name, **argv)

        self.commands.update({'status':     self.statusCmd,
                              'expose':     self.exposeCmd,
                              'dark':       self.darkCmd,
                              'init':       self.initCmd,
                              'raw':        self.doRawCmd
                              })

    
        self.inPath = CPL.cfg.get(self.name, 'inPath')
        self.host = CPL.cfg.get(self.name, 'cameraHost')
        self.port = CPL.cfg.get(self.name, 'cameraPort')

        self._doConnect()

    def zap(self, cmd):
        pass
    
    def _doConnect(self):
        try:
            del self.conn
        except:
            pass
        
        self.conn = GimCtrlConnection.GimCtrlConnection(self.host, self.port)
        self.conn.sendCmd('init', 10)
        self.conn.sendCmd('setcam 1', 20)
        
    def doRawCmd(self, cmd):
        """ Pass on a raw command to our camera. """


        rawCmd = cmd.raw_cmd
        #cmd.warn('debug=%r' % (rawCmd))

        i = rawCmd.index('raw')
        rawCmd = rawCmd[i+4:]
        #space = rawCmd.find(' ')
        #if space >= 0:
        #    rawCmd = rawCmd[space:]
        #cmd.warn('debug=%r' % (rawCmd))
            
        ret = self.sendCmdTxt(rawCmd, 30)
	for i in range(len(ret)):
	    cmd.respond('rawTxt=%s' % (CPL.qstr(ret[i])))
	cmd.finish()
        
    def rawCmd(self, cmd, timeout):
        """ Send a command directly to the controller. """

        cmdStr = cmd.raw_cmd

        # 
        if cmd.program() != "TC01":
            cmdStr.strip()
        #cmd.warn("debug=%r" % (cmdStr))
        
        return self.sendCmdTxt(cmdStr, timeout)
        
    def sendCmdTxt(self, cmdTxt, timeout):
        """ Send a command string directly to the controller. """

        CPL.log("sendTxt", "sending %r" % (cmdTxt))
        ret = self.conn.sendCmd(cmdTxt, timeout)
        CPL.log("sendTxt", "got %r" % (ret))
                
        return ret
        
    def statusCmd(self, cmd, doFinish=True):
        """ Generate status keywords. Does NOT finish teh command.
        """

        if doFinish:
            cmd.finish()

    def getCCDTemp(self):
        """ Return the current CCD temperature. """

        return 0.0
    
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

    def _expose(self, cmd, filename, expType, itime, frame):
        """ Take an exposure of the given length, optionally binned/windowed.

        Args:
            cmd      - the controlling Command.
            filename - the file to save to or None to let us do it dynamically.
            expType  - 'dark' or 'expose'
            itime    - seconds to integrate for
            frame    - ImageFrame

        """

        CPL.log('gcamera', (CPL.qstr("gimctrl expose %s %s secs, frame=%s filename=%s" \
                                     % (expType, itime, frame, filename))))
        
        actor, cmdStr = self.genExposeCommand(cmd, expType, itime, frame)
        ret = self.conn.sendCmd(cmdStr, itime + 15)
        for r in ret:
            if r.find('error') >= 0:
                raise RuntimeError(r)
            
        self.copyinNewRawImage(filename)
        
        return filename

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
    
    def copyinNewRawImage(self, newPath):
        """ Copy (and annotate) the latest raw GimCtrl image into the new directory."""
        
        oldPath = self._getLastImageName()

        CPL.log("copyinNewRawImage", "old=%s; new=%s" % (oldPath, newPath))
        inFITS = pyfits.open(oldPath)
        hdr = inFITS[0].header
        inFITS.writeto(newPath)
        inFITS.close()
        os.chmod(newPath, 0644)
        
        return newPath

# Start it all up.
#
def main(name, eHandler=None, debug=0, test=False):
    camActor = GImCtrlActor(name, debug=debug)
    camActor.start()

    client.run(name=name, cmdQueue=camActor.queue, background=False, debug=debug, cmdTesting=test)
    CPL.log('ecamera.main', 'DONE')

if __name__ == "__main__":
    main('ecamera', debug=6)
