#!/usr/bin/env python

""" The "ecam" command which controls the Echelle slitviewer, currently through
    a GimCtrl Mac
"""

import sys
import time

import client
import CPL
import Guider
import GimGCamera
import TCCGcam

class ecam(Guider.Guider, TCCGcam.TCCGcam):
    """ 
    """
    
    def __init__(self, **argv):
        camera = GimGCamera.GimGCamera('ecam',
                                       '/export/images/guider',
                                       '/export/images/ecam',
                                       **argv)
        Guider.Guider.__init__(self, camera, 'ecam', **argv)

        self._setDefaults()

    def doInit(self, cmd):
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
    
    def doChooseBrain(self, cmd):
        raise NotImplementedError("chooseBrain is not yet implemented")
    
    def doTccDoread(self, cmd):
        """ Pass on a 'doread' command from a TCC to our camera. """

        ret = self.camera.rawCmd(cmd, 120)
        fname = self.camera.copyinNewRawImage()

        cmd.respond('imgFile="%s"' % (fname))
        
        self.echoToTcc(cmd, ret)
    
    def doTccFindstars(self, cmd):
        """ Pass on a 'findstars' command from a TCC to our camera. """

        ret = self.camera.rawCmd(cmd, 15)
        self.echoToTcc(cmd, ret)
    
    def _setDefaults(self):
        self.defaults['bias'] = CPL.cfg.get('ecam', 'bias')
        self.defaults['readNoise'] = CPL.cfg.get('ecam', 'readNoise')
        self.defaults['ccdGain'] = CPL.cfg.get('ecam', 'ccdGain')
        self.defaults['ccdFrame'] = CPL.cfg.get('ecam', 'ccdFrame')
        self.defaults['binning'] = CPL.cfg.get('ecam', 'binning')
        self.defaults['boresight'] = CPL.cfg.get('ecam', 'boresight')
        self.size = self.defaults['ccdFrame'][2:3]
        self.window = [0,0,511,511]

        self.GImName = "S300"
        self.GImCamID = 1

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
