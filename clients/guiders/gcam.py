#!/usr/bin/env python

""" The "gcam" command, which controls the NA2 guider, currently a networked Apogee ALTA.

"""

import os
import sys

import client
import CPL
import Guider
import AltaGCamera
import TCCGcam
import GuideFrame

sys.stderr.write("done imports\n")

class CameraShim(object):
    def __init__(self, name, size, controller):
        self.name = name
        self.size = size
        self.controller = controller

    def statusCmd(self, cmd, doFinish=True):
        cmd.respond('camera="connected"')
        if doFinish:
            cmd.finish()
            
    def cbExpose(self, cmd, cb, type, itime, frame):
        """
        Args:
             cb        callback that gets (filename, frame)
        """

        def _cb(ret):
            CPL.log('cbExpose', '_cb got %s' % (ret))
            filename = ret.KVs.get('camFile', None)
            if not filename:
                cb(None, None)
                return
            filename = cmd.qstr(filename)
            
            frame = GuideFrame.ImageFrame(self.size)
            frame.setImageFromFITSFile(filename)

            cb(cmd, filename, frame)

        client.callback(self.name,
                        '%s exptime=%0.1f bin=%d,%d offset=%d,%d size=%d,%d' % \
                        (type, itime,
                         frame.frameBinning[0], frame.frameBinning[1], 
                         frame.frameOffset[0], frame.frameOffset[1], 
                         frame.frameSize[0], frame.frameSize[1]),
                        cid=self.controller.cidForCmd(cmd),
                        callback=_cb)

    def cbFakefile(self, cmd, cb, filename):
        """
        Args:
             cb        callback that gets (filename, frame)
        """

        def _cb(ret):
            CPL.log('cbFakefile', '_cb got %s' % (ret))
            filename = ret.KVs.get('camFile', None)
            if not filename:
                cb(None, None)
                return

            frame = GuideFrame.ImageFrame(self.size)
            frame.setImageFromFITSFile(filename)

            cb(cmd, filename, frame)

        client.callback(self.name,
                        'expose usefile=%s' % (filename),
                        cid=self.controller.cidForCmd(cmd),
                        callback=_cb)
                         
class gcam(Guider.Guider, TCCGcam.TCCGcam):
    def __init__(self, **argv):
        sys.stderr.write("in gcam.__init__\n")
        ccdSize = CPL.cfg.get('gcam', 'ccdSize')

        path = os.path.join(CPL.cfg.get('gcam', 'imageRoot'), CPL.cfg.get('gcam', 'imageDir'))
        cameraShim = CameraShim('gcamera', ccdSize, self)
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
    main('gcam', debug=6)
