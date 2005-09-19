#!/usr/bin/env python

""" The "nfocus" command, which lets you invoke the PyGuide routines for arbitrary NICFPS images.

"""

import os
import sys

import client
import CPL
import Guider
import GuideFrame
import CameraShim

sys.stderr.write("done imports\n")

class nfocus(Guider.Guider):
    def __init__(self, **argv):
        sys.stderr.write("in nfocus.__init__\n")

        cameraShim = CameraShim.CameraShim('nfake', [1,1], self)
        Guider.Guider.__init__(self, cameraShim, 'nfocus', **argv)
        
    def _setDefaults(self):
        Guider.Guider._setDefaults(self)
        
# Start it all up.
#
def main(name, eHandler=None, debug=0, test=False):
    camActor = nfocus(tccGuider=False, debug=debug)
    camActor.start()

    client.run(name=name, cmdQueue=camActor.queue, background=False, debug=debug, cmdTesting=test)
    CPL.log('nfocus.main', 'DONE')

if __name__ == "__main__":
    main('nfocus', debug=6)
