#!/usr/bin/env python

""" The "gcam" command, which controls the NA2 guider, currently through a GimCtrl Mac via the tcc.

"""

import sys
import time

import client
import CPL
import Guider
import AltaGCamera


class gcam(Guider.Guider):
    def __init__(self, **argv):
        camera = AltaGCamera.AltaGCamera('gcam',
                                         '/export/images/gcam',
                                         'na2alta.apo.nmsu.edu', **argv)
        Guider.Guider.__init__(self, camera, 'gcam', **argv)

        self._setDefaults()
        
    def _setDefaults(self):
        self.boresight = [512.0, 512.0]
        self.size = [1024, 1024]
        self.binning = [3,3]
        self.window = [0,0,340,340]
        self.scanRad = 10.0
        self.guideScale = 0.8
        self.GImName = "Alta-E6"
        self.GImCamID = 0
        
    def _guideExpose(self):
        pass
    
    def _guideOffset(self):
        pass
    
# Start it all up.
#
def main(name, eHandler=None, debug=0, test=False):
    camActor = gcam(tccGuider=True, debug=debug)
    camActor.start()

    client.run(name=name, cmdQueue=camActor.queue, background=False, debug=debug, cmdTesting=test)
    CPL.log('gcam.main', 'DONE')

if __name__ == "__main__":
    main('gcam', debug=6)
