#!/usr/bin/env python

__all__ = ['AltaActor']

import os.path

import client
import Actor
import CPL
import GCamBase
import AltaNet
import GuideFrame

class AltaActor(GCamBase.GCamBase, Actor.Actor):
    """ Use an Alta camera.

    Takes images and puts fleshed out versions into the given public directory.
    
    """
    
    def __init__(self, name, **argv):
        """ Use an Alta camera. """
        
        Actor.Actor.__init__(self, name, **argv)
        GCamBase.GCamBase.__init__(self, name, **argv)

        self.commands.update({'status':     self.statusCmd,
                              'expose':     self.exposeCmd,
                              'dark':       self.darkCmd,
                              'init':       self.initCmd,
                              'setTemp':    self.setTempCmd,
                              'setFan':     self.setFanCmd
                              })
        self._doConnect()
        
    def zap(self, cmd):
        pass
    
    def _doConnect(self):
        """ Create a new, clean connection to the device. """

        try:
            del self.cam
        except:
            pass
        
        hostname = CPL.cfg.get('gcamera', 'cameraHostname')
        self.cam = AltaNet.AltaNet(hostName=hostname)

    def statusCmd(self, cmd, doFinish=True):
        """ Generate status keywords. Does NOT finish the command.
        """

        coolerStatus = self.cam.coolerStatus()
        cmd.respond("%s" % (coolerStatus))

        if doFinish:
            cmd.finish()
            

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
            self.setTemp(cmd, None)
        else:
            try:
                t = float(parts[1])
            except:
                cmd.fail('%sTxt="setTemp value must be \'off\' or a number"')
                return

            self.setTemp(cmd, t)

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

        self.setFan(cmd, t)
            
    def coolerStatus(self, cmd, doFinish=True):
        """ Generate status keywords. Does NOT finish teh command.
        """

        coolerStatus = self.cam.coolerStatus()
        cmd.respond(coolerStatus)

        if doFinish:
            cmd.finish()

    def setTemp(self, cmd, temp, doFinish=True):
        """ Adjust the cooling loop.

        Args:
           cmd  - the controlling command.
           temp - the new setpoint, or None if the loop should be turned off. """

        self.cam.setCooler(temp)
        self.coolerStatus(cmd, doFinish=doFinish)
        
    def setFan(self, cmd, level, doFinish=True):
        """ Adjust the cooling fan level

        Args:
           cmd   - the controlling command.
           level - the new fan level. 0..3
        """

        self.cam.setFan(level)
        self.coolerStatus(cmd, doFinish=doFinish)
        
    def getCCDTemp(self):
        """ Return the current CCD temperature. """

        return self.cam.read_TempCCD()
    
    def _expose(self, cmd, filename, expType, itime, frame):
        """ Take an exposure of the given length, optionally binned/windowed.

        Args:
            cmd      - the controlling Command.
            filename - the file to save to or None to let us do it dynamically.
            expType  - 'dark' or 'expose'
            itime    - seconds to integrate for
            frame    - ImageFrame

        """

        CPL.log('gcamera', (CPL.qstr("alta expose %s %s secs, frame=%s" \
                                     % (expType, itime, frame))))
        
        # Check for format changes:
        bin = frame.frameBinning
        window = list(frame.imgFrameAsWindow())
        CPL.log('gcamera', (CPL.qstr("window = %s" % (window))))
        window = map(int, window)
        
        if bin != self.binning:
            self.cam.setBinning(*bin)
            self.binning = bin
        if window != self.window:
            self.cam.setWindow(*window)
            self.window = window

        doShutter = expType == 'expose'
        if doShutter:
            d = self.cam.expose(itime)
        else:
            d = self.cam.dark(itime)

        self.writeFITS(cmd, frame, d, filename=filename)
        
        # Try hard to recover image memory. 
        del d
        
        return filename

    def writeFITS(self, cmd, frame, d, filename=None):
        """ Write an image to a new FITS file.

        We could use pyfits, but I went for simple...

        Args:
            cmd    - the controlling Command
            frame  - the ImageFrame
            d   - dictionary including:
                     type:     FITS IMAGETYP
                     iTime:    integration time
                     filename: the given filename, or None
                     data:     the image data as a string, or None if saved to a file.

        """

        if filename == None:
            filename = self._getFilename()
            
        f = file(filename, 'w')
        os.chmod(filename, 0644)
        
        basename = os.path.basename(filename)

        binning = frame.frameBinning
        corner, size = frame.imgFrameAsCornerAndSize()
        
        cards = ['SIMPLE  = T',
                 'BITPIX  = 16',
                 'NAXIS   = 2',
                 'NAXIS1  = %d' % (size[0]),
                 'NAXIS2  = %d' % (size[1]),
                 "INSTRUME= '%s'" % (self.name),
                 'BSCALE  = 1.0',
                 'BZERO   = 32768.0',
                 "IMAGETYP= '%s'" % (d['type']),
                 'EXPTIME = %0.2f' % (d['iTime']),
                 "TIMESYS = 'UTC'",
                 "DATE-OBS= '%s'" % (CPL.isoTS(d['startTime'])),
                 "UTMIDDLE= '%s'" % (CPL.isoTS(d['startTime'] + d['iTime']/2.0)),
                 'CCDTEMP = %0.1f' % (self.getCCDTemp()),
                 "FILENAME= '%s'" % (basename),
                 "FULLX   = %d" % (self.ccdSize[0]),
                 "FULLY   = %d" % (self.ccdSize[1]),
                 "BEGX    = %d" % (1 + corner[0]),
                 "BEGY    = %d" % (1 + corner[1]),
                 "BINX    = %d" % (binning[0]),
                 "BINY    = %d" % (binning[1]),
                 'END']

        # Write out all our header cards
        for c in cards:
            f.write("%-80s" % c)

        # Fill the header out to the next full FITS block (2880 bytes, 36 80-byte cards.)
        partialBlock = len(cards) % 36
        if partialBlock != 0:
            blankCard = ' ' * 80
            f.write(blankCard * (36 - partialBlock))

        # Write out the data and fill out the file to a full FITS block.
        f.write(d['data'])
        partialBlock = len(d['data']) % 2880
        if partialBlock != 0:
            f.write(' ' * (2880 - partialBlock))

        f.close()
        
        return filename
    

        
# Start it all up.
#
def main(name, debug=0, test=False):
    camActor = AltaActor('gcamera', debug=debug)
    camActor.start()

    client.run(name=name, cmdQueue=camActor.queue,
               background=False, debug=debug, cmdTesting=test)
    CPL.log('gcamera.main', 'DONE')

if __name__ == "__main__":
    main('gcamera', debug=3)
