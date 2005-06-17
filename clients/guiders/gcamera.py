#!/usr/bin/env python

__all__ = ['AltaActor']

import os.path

import client
import Actor
import CPL
import GCamera
import AltaNet
import GuideFrame

class AltaActor(GCamera.GCamera, Actor.Actor):
    """ Use an Alta camera.

    Takes images and puts fleshed out versions into the given public directory.
    
    """
    
    def __init__(self, name, **argv):
        """ Use an Alta camera. """
        
        self.size = CPL.cfg.get(name, 'ccdSize')
        self.path = CPL.cfg.get(name, 'path')

        Actor.Actor.__init__(self, name, **argv)
        GCamera.GCamera.__init__(self, name, self.path, self.size, **argv)

        self.commands.update({'status':     self.statusCmd,
                              'doread':     self.exposeCmd,
                              'dodark':     self.darkCmd,
                              'expose':     self.exposeCmd,
                              'dark':       self.darkCmd,
                              'init':       self.initCmd,
                              'setTemp':    self.setTempCmd,
                              'setFan':     self.setFanCmd
                              })

        hostname = CPL.cfg.get('gcamera', 'cameraHostname')
        self.cam = AltaNet.AltaNet(hostName=hostname)
        
        # Track binning and window, since we don't want to have to set them for each exposure.
        self.frame = None
        self.binning = [None, None]
        self.window = [None, None, None, None]
    
    def zap(self, cmd):
        pass
    
    def initCmd(self, cmd):
        hostname = CPL.cfg.get('gcamera', 'cameraHostname')
        self.cam = AltaNet.AltaNet(hostName=hostname)
        cmd.finish('text="loaded camera connection"')
        
    def statusCmd(self, cmd):
        self.coolerStatus(cmd)
        
    def exposeCmd(self, cmd):
        """ Take a single guider exposure and return it. 
        """
        
        self.doCmdExpose(cmd, 'expose', {})

    exposeCmd.helpText = ('expose time=S filename=FNAME [window=X0,Y0,X1,Y1] [bin=N] [bin=X,Y]', 
                          'take an open-shutter exposure')

    def darkCmd(self, cmd):
        """ Take a single guider dark and return it. This overrides but
        does not stop the guiding loop.
        """

        self.doCmdExpose(cmd, 'dark', {})
        
    darkCmd.helpText = ('dark time=S filename=FNAME [window=X0,Y0,X1,Y1] [bin=N] [bin=X,Y]',
                        'take a closed-shutter exposure')

    def statusCmd(self, cmd, doFinish=True):
        """ Generate status keywords. Does NOT finish teh command.
        """

        coolerStatus = self.cam.coolerStatus()
        if self.lastImage == None:
            fileStatus = 'lastImage='
        else:
            fileStatus = 'lastImage="%s"' % (self.lastImage)
            
        cmd.respond("%s; %s" % (coolerStatus, fileStatus))

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
    
    def doCmdExpose(self, cmd, type, tweaks):
        """ Parse the exposure arguments and act on them.

        Args:
            cmd    - the controlling Command
            type   - 'object' or 'dark'
            tweaks - dictionary of configuration values.
            
        CmdArgs:
            time   - exposure time, in seconds
            window - subframe, (X0,Y0,X1,Y1)
            bin    - binning, (N) or (X,Y)
            file   - a file name. If specified, the time,window,and bin arguments are ignored.
            
            Returns:
            - a 
        """

        matched, notMatched, leftovers = cmd.match([('time', float), ('exptime', float),
                                                    ('filename', cmd.qstr),
                                                    ('offset', str),
                                                    ('size', str),
                                                    ('window', str),
                                                    ('bin', str),
                                                    ('usefile', cmd.qstr)])
        if matched.has_key('exptime'):
            matched['time'] = matched['exptime']

        # Extra double hack: have a configuration override to the filenames. And
        # if that does not work, look for a command option override.
        filename = None
        if matched.has_key('usefile'):
            filename = matched['usefile']
        
        if filename:

            #if not imgFile:
            #    cmd.fail('text=%s' % (CPL.qstr("No such file: %s" % (filename))))
            #    return
            cmd.finish('camFile=%s' % (filename))
            return
        else:
            if not matched.has_key('time') :
                cmd.fail('text="Exposure commands must specify exposure times"')
                return
            time = matched['time']

            filename = matched.get('filename', None)
            
            if matched.has_key('bin'):
                bin = self.parseBin(matched['bin'])
            else:
                bin = 3,3

            if matched.has_key('offset'):
                offset = self.parseCoord(matched['offset'])
            else:
                offset = 0,0
                
            if matched.has_key('size'):
                size = self.parseCoord(matched['size'])
            else:
                size = self.size

            frame = GuideFrame.ImageFrame(self.size)
            frame.setImageFromFrame(bin, offset, size)

            filename = self._expose(cmd, filename, type, time, frame)
            cmd.finish('camFile=%s' % (filename))

    def _expose(self, cmd, filename, expType, itime, frame):
        """ Take an exposure of the given length, optionally binned/windowed.

        Args:
            cmd      - the controlling Command.
            filename - the file to save to or None to let us do it dynamically.
            expType  - 'dark' or 'expose'
            itime    - seconds to integrate for
            frame    - ImageFrame

        """

        CPL.log('gcamera' % (CPL.qstr("alta expose %s %s secs, frame=%s" \
                                      % (expType, itime, frame))))
        
        # Check format:
        bin = frame.frameBinning
        window = list(frame.imgFrameAsWindow())

        if bin != self.binning:
            self.cam.setBinning(*bin)
            self.binning = bin
        if window != self.window:
            self.cam.setWindow(*window)
            self.window = window

        self.frame = frame
            
        doShutter = expType == 'expose'

        if doShutter:
            d = self.cam.expose(itime)
        else:
            d = self.cam.dark(itime)

        filename = self.writeFITS(cmd, frame, d)
        
        # Try hard to recover image memory. 
        del d
        
        return filename

    def parseWindow(self, w):
        """ Parse a window specification of the form X0,Y0,X1,Y1.

        Args:
           s    - a string of the form "X0,Y0,X1,Y1"

        Returns:
           - the window coordinates, as a 4-tuple of integers.

        Raises:
           Exception on parsing errors.
           
        """

        try:
            parts = w.split(',')
            coords = map(int, parts)
            if len(coords) != 4:
                raise Exception
        except:
            raise Exception("window format must be X0,Y0,X1,Y1 with all coordinates being integers.")

        return coords

    def parseCoord(self, c):
        """ Parse a coordinate pair of the form X,Y.

        Args:
           s    - a string of the form "X,Y"

        Returns:
           - the window coordinates, as a pair of integers.

        Raises:
           Exception on parsing errors.
           
        """

        try:
            parts = c.split(',')
            coords = map(float, parts)
            if len(coords) != 2:
                raise Exception
        except:
            raise Exception("cooordinate format must be X,Y with all coordinates being floats (not %s)." % (parts))

        return coords

    def parseBin(self, s):
        """ Parse a binning specification of the form X,Y or N

        Args:
           s    - a string of the form "X,Y" or "N"

        Returns:
           - the binning factors coordinates, as a duple of integers.

        Raises:
           Exception on parsing errors.
           
        """

        try:
            parts = s.split(',')
            if len(parts) == 1:
                parts = parts * 2
            if len(parts) != 2:
                raise Exception
            coords = map(int, parts)
        except:
            raise Exception("binning must be specified as X,Y or N with all coordinates being integers.")

        return coords
        

        
# Start it all up.
#
def main(name, eHandler=None, debug=0, test=False):
    camActor = AltaActor('gcamera', debug=debug)
    camActor.start()

    client.run(name=name, cmdQueue=camActor.queue, background=False, debug=debug, cmdTesting=test)
    CPL.log('gcamera.main', 'DONE')

if __name__ == "__main__":
    main('gcamera', debug=6)
