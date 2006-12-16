#!/usr/bin/env python

""" The "ecam" command which controls the Echelle slitviewer, currently through
    a GimCtrl Mac
"""

import os
import sys

import client
import CPL
import Guider
import TCCGcam
import GuideFrame
import CameraShim
import Parsing

class ecam(Guider.Guider, TCCGcam.TCCGcam):
    def __init__(self, **argv):
        ccdSize = CPL.cfg.get('ecamera', 'ccdSize')
        cameraShim = CameraShim.CameraShim('ecamera', ccdSize, self)
        Guider.Guider.__init__(self, cameraShim, 'ecam', **argv)
        TCCGcam.TCCGcam.__init__(self, **argv)

        # Addition commands for GimCtrl camera
        self.commands.update({'rawCmd':    self.doRawCmd,
                              'doMakeMask': self.doMakeMask})

        self.rawPath = CPL.cfg.get(self.name, 'rawPath')
        
    def _setDefaults(self):
        Guider.Guider._setDefaults(self)
        
        self.GImName = "S300"
        self.GImCamID = 1

    def doTccInit(self, cmd):
        """ Pass on an 'init' command from a TCC to our camera. """
        
        ret = self.rawCmd(cmd, 10)
        self.echoToTcc(cmd, ret)
    
    def doTccSetcam(self, cmd):
        """ Pass on a 'setcam' command from a TCC to our camera. """

        ret = self.rawCmd(cmd, 30)
        self.echoToTcc(cmd, ret)
    
    def doTccShowstatus(self, cmd):
        """ Pass on a 'setcam' command from a TCC to our camera. """

        ret = self.rawCmd(cmd, 10)
        self.echoToTcc(cmd, ret)
    
    def rawCmd(self, cmd, timeout=30):

        cmdTxt = cmd.raw_cmd
        #cmd.warn("debug=%r" % (cmdTxt))
        
        ret = self.rawTxtCmd(cmdTxt, timeout=timeout)
        CPL.log('ecamCMDDEBUG', "%r" % (ret))
        
        return ret
    
    def rawTxtCmd(self, rawCmd, timeout=30):
        ret = client.call('ecamera', 'raw %s' % (rawCmd),
                          cid="XX01.me")
        CPL.log('ecamDEBUG', "ret=%r" % (ret.lines))
        lines = []
        for r in ret.lines:
            if r.KVs.has_key('rawTxt'):
                t = r.KVs['rawTxt']
                lines.append(Parsing.dequote(t))
        CPL.log('ecamDEBUG', "lines=%r" % (lines))
        return lines
        
    def doRawCmd(self, cmd):
        """ Pass on a raw command to our camera. """

        rawCmd = cmd.raw_cmd
        space = rawCmd.find(' ')
        if space >= 0:
            rawCmd = rawCmd[space:]

        ret = self.rawTxtCmd(rawCmd)
        CPL.log('ecamCMDDEBUG', "%r" % (ret))
        # cmd.warn("cmddebug=%r" % (ret))
	for i in range(len(ret)):
	    cmd.respond(ret[i])
	cmd.finish()

    def getLastPath(self):
        """ Return the full path of the last file written """

        f = open(os.path.join(self.rawPath, "last.image"), "r")
        lastFile = f.read()
        f.close()

        lastPath = os.path.join(self.rawPath, lastFile)

        return lastPath
    
    def doTccDoread(self, cmd):
        """ Pass on a 'doread' command from a TCC to our camera. """

        # Parse the tcc command. It will _always_ have all fields
        #
        try:
            exptype, iTime, xBin, yBin, xCtr, yCtr, xSize, ySize = cmd.raw_cmd.split()
        except:
            cmd.fail('txtForTcc=%s' % (CPL.qstr("Could not parse command %s" % (cmd.raw_cmd))))
            return

        ret = self.rawCmd(cmd, float(iTime) + 20)
        fname = self.getLastPath()
        cmd.respond('camFile="%s"' % (fname))
        frame = GuideFrame.ImageFrame(self.size)
        frame.setImageFromFITSFile(fname)

        self.frameForTcc = frame
        self.fileForTcc = fname
        
        self.echoToTcc(cmd, ret)
    
    def doMakeMask(self, cmd):
        """ Build and install a new mask file.

        Assume the following:
          - na1 eyelid open
          - Bright Quartz truss lamp on

        Take 3 flats, then call an external .pro file to mangle it.

        """

        pass
    

# Start it all up.
#
def main(name, eHandler=None, debug=0, test=False):
    camActor = ecam(debug=debug, host='apots2.apo.nmsu.edu', port=3009)
    camActor.start()

    client.run(name=name, cmdQueue=camActor.queue,
               background=False, debug=debug, cmdTesting=test)
    CPL.log('ecam.main', 'DONE')

if __name__ == "__main__":
    main('ecam', debug=3)
