#!/usr/bin/env python

""" 
The "tcam" command, which controls the TripleSpec slitviewer, 
over a socket. 
"""

import os
import sys
import time
import math
from traceback import format_exc
import pyfits

import client
import CPL
import Parsing
import Guider
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
    def __init__(self, name, size, controller):
        CameraShim.CameraShim.__init__(self, name, size, controller)
        self.expose_in_progress = False
        self.state = 'idle'
        self.length = 0.
        self.left = 0.
        self.mark = time.time()

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

    def cbMessage(self, cmd):
        now = time.time()
        if self.state in ('idle', 'done', 'aborted'):
            times = [0.0, 0.0]
        else:
            left = (self.mark + self.length) - now
            times = [left, self.length]
            
        markString = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(self.mark)) \
                     + ".%1dZ" % (10 * math.modf(self.mark)[0])
        
        if times[0] < 0.0:
            times[0] = 0.0
        if times[1] < 0.0:
            times[1] = 0.0
            
        return "expState=%s,%s,%0.1f,%0.1f" % \
               (CPL.qstr(self.state),
                markString, times[0], times[1])
            
    def cbExpose(self, cmd, cb, type, itime, frame, filename=None):
        """
        Args:
             cb        callback that gets (filename, frame)
        """

        self.expose_in_progress = True
        self.stateMark = time.time()

        def _cb(ret, parent=self,cmd=cmd):
            CPL.log('cbExpose', '_cb got %s' % (ret))
            CPL.log('cbExpose', '_cb got %s' % (str(ret.KVs)))

            expose_state = ret.KVs.get('exposureState', None)

            if expose_state:
                try:
                    state, length, left = expose_state
                    parent.length = float(length)
                    parent.left = float(left)
                    parent.mark = time.time() - parent.length + parent.left
                    parent.state = state.replace('"','')

                    # tell TUI the expose state
                    cmd.respond(parent.cbMessage(cmd))
                    if parent.state == 'done':
                        parent.expose_in_progress = False
                except:
                    CPL.log('cbExpose', 'exception %s' % (format_exc()))
                    cb(cmd, None, None, failure='exposure failed')
                    return

            if parent.expose_in_progress:
                return
            
            camFilename = ret.KVs.get('camFile', None)
            if not camFilename:
                cb(cmd, None, None, failure='exposure failed')
                return
            camFilename = cmd.qstr(camFilename)
            
            frame = GuideFrame.ImageFrame(self.size)
            frame.setImageFromFITSFile(camFilename)

            cb(cmd, camFilename, frame)

        client.callback(self.name,
                        '%s exptime=%0.1f bin=%d,%d offset=%d,%d size=%d,%d filename=%s' % \
                        (type, itime,
                         frame.frameBinning[0], frame.frameBinning[1], 
                         frame.frameOffset[0], frame.frameOffset[1], 
                         frame.frameSize[0], frame.frameSize[1],
                         filename),
                        cid=self.controller.cidForCmd(cmd),
                        callback=_cb,
                        dribble=True)


class tcam(Guider.Guider):
    def __init__(self, **argv):
        ccdSize = CPL.cfg.get('tcam', 'ccdSize')

        path = os.path.join(CPL.cfg.get('tcam', 'imageRoot'), CPL.cfg.get('tcam', 'imageDir'))
        cameraShim = TCameraShim('tcamera', ccdSize, self)
        Guider.Guider.__init__(self, cameraShim, 'tcam', **argv)

        self.commands.update({'gain':     self.setGainTable})
        self.mask_type = "on"
        

    def setGainTable(self, cmd):
        """ change gain table to be either off or on.

        CmdArgs:
            type - off or on
        """

        try:
            mask_type = cmd.argDict['gain'].replace('"','')
        except:
            cmd.fail('text="usage: gain=type, type is on or off"')
            return

        if mask_type not in ['off', 'on']:
            cmd.fail('text="usage: gain=type, type is on or off"')
            return

        self.mask_type = mask_type

    setGainTable.helpText = ('gain=type',
                           'set the gain table to be either on or off')
        
    def processCamFile(self, cmd, camFile, tweaks, frame=None):
        """ Given a raw cameraFile, optionally dark-subtract or flat-field.

        Args:
             cmd         - the controlling Command
             camFile     - a raw file from a camera.
             tweaks      - our configuration
             frame       ? an ImageFrame describing the camFile

        Returns:
             - the processed filename (possibly just camFile)
             - the matching maskFile
             - the dark file used (or None)
             - the flat file used (or None)

        """

        t0 = time.time()

        # Maybe camFile is not a raw file, but an already processed file. Detect this, and force
        # the real raw file to be re-processed.
        head, tail = os.path.split(camFile)
        if tail.find('proc-') == 0:
            camFile = os.path.join(head, tail[5:])
            
        camFITS = pyfits.open(camFile) 
        camBits = camFITS[0].data
        camHeader = camFITS[0].header
        camFITS.close()
        size = camBits.shape
            
        if not frame:
            frame = GuideFrame.ImageFrame(self.size)
            frame.setImageFromFITSFile(camFile)

        maskFile, maskBits = self.mask.getMaskForFrame(cmd, camFile, frame)

        darkFile = self.getDarkForCamFile(cmd, camFile, tweaks)
            
        if tweaks.get('doFlatfield'):
            flatFile = maskFile
        else:
            flatFile = None

        # Make blank masks
        satMaskArray = camBits * 0
        maskArray = camBits * 0

        # Scale pixel values by binning - 20080403 FRS
        bin = tweaks.get('bin', [1,1])
        scale = bin[0]*bin[1]
        if scale > 1:
            camBits /= scale
        
        # Dark or bias subtraction.
        if darkFile:
            darkFITS = pyfits.open(darkFile)
            darkBits = darkFITS[0].data
            darkFITS.close()

            x0, y0, x1, y1 = frame.imgFrameAsWindow(inclusive=False)
            darkBits = darkBits[y0:y1, x0:x1]
        else:
            # Need to do better at figuring the bias level. These cameras don't seem
            # to have overscan regions, though!
            #
            darkBits = camBits * 0.0 + tweaks['bias']

        if camBits.shape != darkBits.shape:
            cmd.warn('debug="cam=%s dark=%s"' % (camBits.shape, darkBits.shape))

        # Set aside the saturated pixel mask:
        saturation = tweaks['saturation']
        satmaskArray = camBits >= saturation
        camBits -= darkBits

        if flatFile:
            #
            # The flatfile has two bits of info embedded in it:
            #   - the flatfield, where the values are > 0
            #   - a mask, where the flatfield values are 0
            #
            maskArray = maskBits == 0
            if self.mask_type == "on":
                # add 1s to the place where the maskBits are 0 so the ff
                # at least preserves the pixels.  I don't know the reason for 
                # this, because flatArray is multiplied rather than divided.
                flatArray = maskBits + maskArray

                # There are some cases where the ff is bad, and will result in
                # min/max outliers which totally blow the scaling.  What should
                # be done about these?
                camBits *= flatArray

        camBits = self.trimToInt16(cmd, camBits, saturation)
        procFile = self.changeFileBase(camFile, "proc-", prepend=True)

        self.writeProcFile(cmd, procFile, camHeader, camBits, (maskArray, satmaskArray))

        del darkBits
        del camBits
        del maskBits
            
        t1 = time.time()

        # ???
        if darkFile and darkFile.find('bias') > -1:
            darkFile = None
            
        return procFile, maskFile, darkFile, flatFile
        

    def _setDefaults(self):

        Guider.Guider._setDefaults(self)

        self.GImName = "tcamera"
        self.GImCamID = 1
        
    def run(self):
        client.listenFor('tcamera', ['slitPosition','slitState'], self.listenToMaskName)
        client.call('tcamera', 'slitStatus')

        Guider.Guider.run(self)
        
    def listenToMaskName(self, reply):
        """
        """

        CPL.log('tcam', 'in listenToMaskName=%s' % (reply,))
        slitDone = reply.KVs.get('slitState', None)
        if not slitDone:
            return

        try:
            slitDone = slitDone[0].replace('"','')

            slitmaskName = reply.KVs.get('slitPosition', '').replace('"','')
            CPL.log('tcam', 'in listenToMaskName=%s, done %s, position %s' % (reply, slitDone,slitmaskName))

            if slitDone == "done":
                slitmaskName = Parsing.dequote(slitmaskName)

                slitmaskName = slitmaskName.replace(' ', '-')
                maskdir, dummy = os.path.split(self.config['maskFile'])
                maskfileName = os.path.join(maskdir, slitmaskName) + ".fits"
         
                CPL.log('tcam', 'slit=%s maskfile=%s' % (slitmaskName, maskfileName))
            else:
                return

            self._setMask(None, maskfileName)
        except:
            pass
        
    def genFilename(self):
        return self._getFilename()
    
# Start it all up.
#
def main(name, eHandler=None, debug=0, test=False):
    camActor = tcam(tccGuider=False, debug=debug)
    client.init(name=name, cmdQueue=camActor.queue, background=False, debug=debug, cmdTesting=test)

    camActor.start()
    client.run(name=name, cmdQueue=camActor.queue, background=False, debug=debug, cmdTesting=test)
    CPL.log('tcam.main', 'DONE')

if __name__ == "__main__":
    main('tcam', debug=3)
