#!/usr/bin/env python

""" The "nfocus" command, which lets you invoke the PyGuide routines for arbitrary spicam images.

"""

import os
import sys

import client
import CPL
import Guider
import GuideFrame
import CameraShim

sys.stderr.write("done imports\n")

class sfocus(Guider.Guider):
    def __init__(self, **argv):
        sys.stderr.write("in sfocus.__init__\n")

        cameraShim = CameraShim.CameraShim('nfake', [1,1], self)
        argv['instName'] = 'spicam'     # Override what we expect to see in the fits INSTRUME card.
        Guider.Guider.__init__(self, cameraShim, 'sfocus', **argv)
        
    def _setDefaults(self):
        Guider.Guider._setDefaults(self)
        
# Start it all up.
#
def main(name, eHandler=None, debug=0, test=False):
    camActor = sfocus(tccGuider=False, debug=debug)
    camActor.start()

    client.run(name=name, cmdQueue=camActor.queue, background=False, debug=debug, cmdTesting=test)
    CPL.log('sfocus.main', 'DONE')

if __name__ == "__main__":
    main('sfocus', debug=3)
