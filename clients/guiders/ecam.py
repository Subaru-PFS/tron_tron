#!/usr/bin/env python

""" The "ecam" command, which controls the Echelle slitviewer, currently through
    a GimCtrl Mac via the tcc.
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
        camera = GimGCamera.GimGCamera('ecam', 'ecam',
                                       '/export/images/guider',
                                       '/export/images/ecam',
                                       True, **argv)
        Guider.Guider.__init__(self, camera, 'ecam', **argv)

        self._setDefaults()
        
    def _setDefaults(self):
        self.boresightPixel = [286.0, 222.0]
        self.binning = [1,1]
        self.scanRad = 25.0
        self.guideScale = 0.8
        
        
# Start it all up.
#
def main(name, eHandler=None, debug=0, test=False):
    camActor = ecam(debug=debug)
    camActor.start()

    client.run(name=name, cmdQueue=camActor.queue,
               background=False, debug=debug, cmdTesting=test)
    CPL.log('ecam.main', 'DONE')

if __name__ == "__main__":
    main('ecam', debug=6)
