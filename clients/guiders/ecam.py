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


class ecam(Guider.Guider):
    """ 
    """
    
    def __init__(self, **argv):
        camera = GimGCamera.GimGCamera('ecam',
                                       '/export/images/guider',
                                       '/export/images/ecam',
                                       **argv)
        Guider.Guider.__init__(self, camera, 'ecam', **argv)

        # Additional commands for the Alta.
        #
        self.commands.update({'chooseBrain':  self.doChooseBrain})
        self.brain = 'mac'
        
        self._setDefaults()

    def doChooseBrain(self, cmd):
        raise NotImplementedError("chooseBrain is not yet implemented")
    
    def doTccDoread(self, cmd):
        """ Pass on a 'doread' command from a TCC to our camera. """

        ret = self.camera.rawCmd(cmd, 120)
        fname = self.camera.copyinNewRawImage()

        cmd.respond('filename="%s"' % (fname))
        
        self.echoToTcc(cmd, ret)
    
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
    
    def doTccFindstars(self, cmd):
        """ Pass on a 'findstars' command from a TCC to our camera. """

        ret = self.camera.rawCmd(cmd, 15)
        self.echoToTcc(cmd, ret)
    
    def _setDefaults(self):
        self.boresightPixel = [286.0, 222.0]
        self.size = [512, 512]
        self.window = [0,0,511,511]
        self.binning = [1,1]
        self.scanRad = 25.0
        self.guideScale = 0.8
        self.GImName = "S300"
        self.GImCamID = 1
        self.plateScale = 0.134

        self.bias = 1787
        self.rdNoise = 7.9
        self.ccdGain = 4.6
        self.starThresh = 4.5
        self.defaultStarThresh = self.starThresh
        
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
