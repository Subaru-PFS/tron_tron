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

class dcam(Guider.Guider, TCCGcam.TCCGcam):
    def __init__(self, **argv):
        ccdSize = CPL.cfg.get('dcam', 'ccdSize')

        path = os.path.join(CPL.cfg.get('dcam', 'imageRoot'), CPL.cfg.get('dcam', 'imageDir'))
        cameraShim = CameraShim.CameraShim('dcamera', ccdSize, self)
        Guider.Guider.__init__(self, cameraShim, 'dcam', **argv)
        TCCGcam.TCCGcam.__init__(self, **argv)

    def _setDefaults(self):

        Guider.Guider._setDefaults(self)

        self.GImName = "Apogee"
        self.GImCamID = 1
        
    def run(self):
        '''
        Call the guider loop.  First, get the tspec status and find out the
        slit and generate the maks name to use.
        '''
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
    
# Start it all up.
#
def main(name, eHandler=None, debug=0, test=False):
    camActor = dcam(tccGuider=True, debug=debug)
    client.init(name=name, cmdQueue=camActor.queue, background=False, debug=debug, cmdTesting=test)

    camActor.start()
    client.run(name=name, cmdQueue=camActor.queue, background=False, debug=debug, cmdTesting=test)
    CPL.log('dcam.main', 'DONE')

if __name__ == "__main__":
    main('dcam', debug=3)
