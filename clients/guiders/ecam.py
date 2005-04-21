#!/usr/bin/env python

""" The "ecam" command which controls the Echelle slitviewer, currently through
    a GimCtrl Mac
"""

import os
import sys

import client
import CPL
import Guider
import GimCtrlGCamera
import TCCGcam
import GuideFrame

class ecam(Guider.Guider, TCCGcam.TCCGcam):
    """ 
    """
    
    def __init__(self, **argv):
        ccdSize = CPL.cfg.get('ecam', 'ccdSize')

        path = os.path.join(CPL.cfg.get('ecam', 'imageRoot'), CPL.cfg.get('ecam', 'imageDir'))
        camera = GimCtrlGCamera.GimCtrlGCamera('ecam',
                                               '/export/images/guider', path,
                                               ccdSize,
                                               **argv)
        Guider.Guider.__init__(self, camera, 'ecam', **argv)
        TCCGcam.TCCGcam.__init__(self, **argv)

        self.commands.update({'rawCmd':    self.doRawCmd})
        
    def _setDefaults(self):
        Guider.Guider._setDefaults(self)
        
        self.GImName = "S300"
        self.GImCamID = 1

    def initCmd(self, cmd):
        """ Pass on an 'init' command from a TCC to our camera. """
        
        ret = self.camera.rawCmd(cmd, 10)
        self.echoToTcc(cmd, ret)
    
    def doTccSetcam(self, cmd):
        """ Pass on a 'setcam' command from a TCC to our camera. """

        ret = self.camera.rawCmd(cmd, 30)
        self.echoToTcc(cmd, ret)
    
    def doTccShowstatus(self, cmd):
        """ Pass on a 'setcam' command from a TCC to our camera. """

        ret = self.camera.rawCmd(cmd, 10)
        self.echoToTcc(cmd, ret)
    
    def doRawCmd(self, cmd):
        """ Pass on a raw command to our camera. """

        rawCmd = cmd.raw_cmd
        space = rawCmd.find(' ')
        if space >= 0:
            rawCmd = rawCmd[space:]
            
        ret = self.camera.sendCmdTxt(rawCmd, 30)
	for i in range(len(ret)):
	    cmd.respond('rawTxt=%s' % (CPL.qstr(ret[i])))
	cmd.finish()
    
    def doTccDoread(self, cmd):
        """ Pass on a 'doread' command from a TCC to our camera. """

        # Parse the tcc command. It will _always_ have all fields
        #
        try:
            exptype, iTime, xBin, yBin, xCtr, yCtr, xSize, ySize = cmd.raw_cmd.split()
        except:
            cmd.fail('txtForTcc=%s' % (CPL.qstr("Could not parse command %s" % (cmd.raw_cmd))))
            return

        ret = self.camera.rawCmd(cmd, 120)
        fname = self.camera.copyinNewRawImage()
        frame = GuideFrame.ImageFrame(self.size)
        frame.setImageFromFITSFile(fname)

        self.imgForTcc = fname
        self.frameForTcc = frame
        self.fileForTcc = fname
        
        cmd.respond('camFile="%s"' % (fname))
        
        self.echoToTcc(cmd, ret)
    

# Start it all up.
#
def main(name, eHandler=None, debug=0, test=False):
    camActor = ecam(debug=debug, host='apots2.apo.nmsu.edu', port=3009)
    camActor.start()

    client.run(name=name, cmdQueue=camActor.queue,
               background=False, debug=debug, cmdTesting=test)
    CPL.log('ecam.main', 'DONE')

if __name__ == "__main__":
    main('ecam', debug=6)
