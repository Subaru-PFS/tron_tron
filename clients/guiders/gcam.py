#!/usr/bin/env python

""" The "gcam" command, which controls the NA2 guider, currently a networked Apogee ALTA.

"""

import os
import sys

import client
import CPL
import Guider
import TCCGcam
import GuideFrame
import CameraShim

sys.stderr.write("done imports\n")

class gcam(Guider.Guider, TCCGcam.TCCGcam):
    def __init__(self, **argv):
        sys.stderr.write("in gcam.__init__\n")
        ccdSize = CPL.cfg.get('gcam', 'ccdSize')

        cameraShim = CameraShim.CameraShim('gcamera', ccdSize, self)
        Guider.Guider.__init__(self, cameraShim, 'gcam', **argv)
        TCCGcam.TCCGcam.__init__(self, **argv)
        
        # Additional commands for the Alta.
        #
        self.commands.update({'setTemp':    self.setTempCmd,
                              'setFan':     self.setFanCmd})

    def _setDefaults(self):

        Guider.Guider._setDefaults(self)
        
        self.GImName = "Alta-E6"
        self.GImCamID = 1

    def setTempCmd(self, cmd):
        """ Handle setTemp command.

        CmdArgs:
           float    - the new setpoint. Or "off" to turn the loop off. 
        """

        parts = cmd.raw_cmd.split()
        if len(parts) != 2:
            cmd.fail('%sTxt="usage: setTemp value."')
            return

        if parts[1] == 'off':
            self.camera.setTemp(cmd, None)
        else:
            try:
                t = float(parts[1])
            except:
                cmd.fail('%sTxt="setTemp value must be \'off\' or a number"')
                return

            self.camera.setTemp(cmd, t)

        self.camera.coolerStatus(cmd)
        cmd.finish()
            
    def setFanCmd(self, cmd):
        """ Handle setFan command.

        CmdArgs:
           int    - the new fan level. 0-3
        """

        parts = cmd.raw_cmd.split()
        if len(parts) != 2:
            cmd.fail('%sTxt="usage: setFan value."')
            return

        try:
            t = int(parts[1])
            assert t in (0,1,2,3)
        except:
            cmd.fail('%sTxt="setFan value must be 0..3"')
            return

        self.camera.setFan(cmd, t)

        self.camera.coolerStatus(cmd)
        cmd.finish()
            
# Start it all up.
#
def main(name, eHandler=None, debug=0, test=False):
    camActor = gcam(tccGuider=True, debug=debug)
    camActor.start()

    client.run(name=name, cmdQueue=camActor.queue, background=False, debug=debug, cmdTesting=test)
    CPL.log('gcam.main', 'DONE')

if __name__ == "__main__":
    main('gcam', debug=3)
