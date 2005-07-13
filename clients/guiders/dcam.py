#!/usr/bin/env python

""" The "dcam" command, which controls the DIS slitviewer, over a socket. """

import os
import sys

import client
import CPL
import Parsing
import Guider
import TCCGcam
import GuideFrame
import CameraShim

sys.stderr.write("done imports\n")

class dcam(Guider.Guider, TCCGcam.TCCGcam):
    def __init__(self, **argv):
        ccdSize = CPL.cfg.get('dcam', 'ccdSize')

        path = os.path.join(CPL.cfg.get('dcam', 'imageRoot'), CPL.cfg.get('dcam', 'imageDir'))
        cameraShim = CameraShim.CameraShim('dcamera', ccdSize, self)
        Guider.Guider.__init__(self, cameraShim, 'dcam', **argv)
        TCCGcam.TCCGcam.__init__(self, **argv)
        
        # Additional commands for the DIS slitviewer.
        #
        self.commands.update({'setTemp':    self.setTempCmd,
                              'setFan':     self.setFanCmd})

    def run(self):
        client.listenFor('dis', ['maskName'], self.listenToMaskName)
        client.call('dis', 'status')

        Guider.Guider.run(self)
        
    def listenToMaskName(self, reply):
        """
        """

        CPL.log('dcam', 'in listenToMaskName=%s' % (reply))

        slitmaskName = reply.KVs.get('maskName', '')
        slitmaskName = Parsing.dequote(slitmaskName)

        slitmaskName = slitmaskName.replace(' ', '')
        maskdir, dummy = os.path.split(self.config['maskFile'])
        maskfileName = os.path.join(maskdir, slitmaskName) + ".fits"
        
        CPL.log('dcam', 'slit=%s maskfile=%s' % (slitmaskName, maskfileName))

        self._setMask(None, maskfileName)
        
        
    def genFilename(self):
        return self._getFilename()
    
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
    camActor = dcam(tccGuider=True, debug=debug)
    client.init(name=name, cmdQueue=camActor.queue, background=False, debug=debug, cmdTesting=test)

    camActor.start()
    client.run(name=name, cmdQueue=camActor.queue, background=False, debug=debug, cmdTesting=test)
    CPL.log('dcam.main', 'DONE')

if __name__ == "__main__":
    main('dcam', debug=6)
