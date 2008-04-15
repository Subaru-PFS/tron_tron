#!/usr/bin/env python

""" 
The "tcam" command, which controls the TripleSpec slitviewer, 
over a socket. 
"""

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

#from traceback import print_exc
#LOGFD = file('/home/tron/logfile', 'w')

def DEBUG(msg):
    '''Debug print message to a file'''
    #LOGFD.write(msg+'\n')
    #LOGFD.flush()
    pass

def DEBUG_EXC():
    '''Debug print stack trace to a file'''
    #print_exc(file=LOGFD)
    #LOGFD.flush()
    pass

class TCameraShim (CameraShim.CameraShim):

    def cbFakefile(self, cmd, cb, filename):
        """
        Args:
             cb        callback that gets (filename, frame)
        """
        if not filename:
            cb(None, None, failure='no such file')
            return

        frame = GuideFrame.ImageFrame(self.size)
        frame.setImageFromFITSFile(filename)

        cb(cmd, filename, frame)


#class tcam(Guider.Guider):
class tcam(Guider.Guider):
    def __init__(self, **argv):
        ccdSize = CPL.cfg.get('tcam', 'ccdSize')

        path = os.path.join(CPL.cfg.get('tcam', 'imageRoot'), CPL.cfg.get('tcam', 'imageDir'))
        cameraShim = TCameraShim('tcamera', ccdSize, self)
        Guider.Guider.__init__(self, cameraShim, 'tcam', **argv)

    def _setDefaults(self):

        Guider.Guider._setDefaults(self)

        self.GImName = "tcamera"
        self.GImCamID = 1
        
    def run(self):
        client.listenFor('tspec', ['maskName'], self.listenToMaskName)
        #client.call('tspec', 'status')

        Guider.Guider.run(self)
        
    def listenToMaskName(self, reply):
        """
        """

        CPL.log('tcam', 'in listenToMaskName=%s' % (reply))

        slitmaskName = reply.KVs.get('maskName', '')
        slitmaskName = Parsing.dequote(slitmaskName)

        slitmaskName = slitmaskName.replace(' ', '')
        maskdir, dummy = os.path.split(self.config['maskFile'])
        maskfileName = os.path.join(maskdir, slitmaskName) + ".fits"
        
        CPL.log('tcam', 'slit=%s maskfile=%s' % (slitmaskName, maskfileName))

        self._setMask(None, maskfileName)
        
    def genFilename(self):
        return self._getFilename()
    
# Start it all up.
#
def main(name, eHandler=None, debug=0, test=False):
    camActor = tcam(tccGuider=True, debug=debug)
    client.init(name=name, cmdQueue=camActor.queue, background=False, debug=debug, cmdTesting=test)

    camActor.start()
    client.run(name=name, cmdQueue=camActor.queue, background=False, debug=debug, cmdTesting=test)
    CPL.log('tcam.main', 'DONE')

if __name__ == "__main__":
    main('tcam', debug=3)
