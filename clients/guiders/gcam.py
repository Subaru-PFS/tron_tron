#!/usr/bin/env python

""" The "gcam" command, which controls the NA2 guider, currently a networked Apogee ALTA.

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

        # Additional commands for the Alta.
        #
        self.commands.update({'setTemp':    self.doSetTemp,
                              'setFan':     self.doSetFan})

        self._setDefaults()
        
    def _setDefaults(self):
        self.boresight = [512.0, 512.0]
        self.size = [1024, 1024]
        self.binning = [3,3]
        self.window = [0,0,340,340]
        self.scanRad = 10.0
        self.guideScale = 0.8
        self.GImName = "Alta-E6"
        self.GImCamID = 1

    def doSetTemp(self, cmd):
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
            
    def doSetFan(self, cmd):
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
