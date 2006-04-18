__all__ = ['GCamBase']

""" GCamBase.py -- base guide camera controllers.

    A "guide camera" is a _simple_ device. It can:
     - expose for S seconds
    
    It can optionally:
     - take S seconds darks
     - window and bin both exposures and darks.

    The images are saved to disk, using the date as a filename.
"""

import os.path
import time

import CPL
import GuideFrame

class GCamBase(object):
    def __init__(self, name, **argv):
        """ Create a GCamBase instance.

        Args:
             name        - a unique, human-readable name.
        """
        
        self.name = name
        self.nameChar = name[0]
        
        self.ccdSize = CPL.cfg.get(name, 'ccdSize')
        self.path = CPL.cfg.get(name, 'path')

        # Basic sanity checks _now_
        #
        if not os.path.isdir(self.path):
            raise RuntimeError("path given to %s is not a directory: %s" % (name, path))
        # Track binning and window, since we don't necessarily
        # want to have to set them for each exposure.
        self.binning = [None, None]
        self.window = [None, None, None, None]
    
        self.lastImage = None
        self.lastDir = None
        self.lastID = None

        CPL.log("GCamBase", "after init: %s" % (self))
        
    def __str__(self):
        return "GCamBase(name=%s, ccdSize=%s, path=%s)" % (self.name, self.ccdSize, self.path)
    
    def initCmd(self, cmd, doFinish=True):
        self._doConnect()
        cmd.finish('text="loaded camera connection"')

        if doFinish:
            cmd.finish()
            
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

    def doCmdExpose(self, cmd, type, tweaks):
        """ Parse the exposure arguments and act on them.

        Args:
            cmd    - the controlling Command
            type   - 'object' or 'dark'
            tweaks - dictionary of configuration values.
            
        CmdArgs:
            time   - exposure time, in seconds. exptime iis an alias, for som reason.
            window - subframe, (X0,Y0,X1,Y1)
            bin    - binning, (N) or (X,Y)
            offset - the LL pixel to acquire. (X,Y)
            size   - the size of the rectangle to acquire. (X,Y)
            usefile - an existing full path name.
                        If specified, the time,window,and bin arguments are ignored,
                        and the given file is simply returned.

        Cmd
            
            Returns:
            - a 
        """

        matched, notMatched, leftovers = cmd.match([('time', float), ('exptime', float),
                                                    ('bin', str),
                                                    ('offset', str),
                                                    ('size', str),
                                                    ('filename', cmd.qstr),
                                                    ('usefile', cmd.qstr)])
        if matched.has_key('exptime'):
            matched['time'] = matched['exptime']

        # Extra double hack: use a disk file instead of acquiring a new image
        if matched.has_key('usefile'):
            filename = matched['usefile']
            cmd.finish('camFile=%s' % (filename))
            return

        if not matched.has_key('filename') :
            cmd.fail('text="Exposure commands must specify a filename"')
            return
        filename = matched['filename']
        
        if not matched.has_key('time') :
            cmd.fail('text="Exposure commands must specify exposure times"')
            return
        time = matched['time']

        if matched.has_key('bin'):
            bin = self.parseBin(matched['bin'])
        else:
            bin = 1,1

        if matched.has_key('offset'):
            offset = self.parseCoord(matched['offset'])
        else:
            offset = 0,0
                
        if matched.has_key('size'):
            size = self.parseCoord(matched['size'])
        else:
            size = self.ccdSize

        frame = GuideFrame.ImageFrame(self.ccdSize)
        frame.setImageFromFrame(bin, offset, size)

        try:
            filename = self._expose(cmd, filename, type, time, frame)
            cmd.finish('camFile=%s' % (filename))
        except Exception, e: 
            cmd.fail('text=%s' % (CPL.qstr(e)))
           

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
        
    def _getFilename(self):
        """ Return the next available filename.

        We try to not suffer collisions by putting the files in per-day directories.

        This is where we create any necessary directories. And we do that expensively,
        by checking for each file whether the right directory exists.

        We want the directories to change at local noon and be named after the
        new day's date. 
        """

        dateString = CPL.getDayDirName()
        dirName = os.path.join(self.path, dateString)
        if not os.path.isdir(dirName):
            os.mkdir(dirName)
            os.chmod(dirName, 0755)

            id = 1
            fileName = "%s%04d.fits" % (self.nameChar, id)
            
            # Create the last.image file
            #
            f = open(os.path.join(dirName, "last.image"), "w+")
            f.write('%s\n' % (fileName))
            f.close()
        else:
            # Update the last.image file
            #
            f = open(os.path.join(dirName, "last.image"), "r+")
            lastFileName = f.readline()
            lastID = int(lastFileName[1:5], 10)
            id = lastID + 1
            
            if id > 9999:
                raise RuntimeError("guider image number in %s is more than 9999." % (dirName))
            
            fileName = "%s%04d.fits" % (self.nameChar, id)

            f.seek(0,0)
            f.write('%s\n' % (fileName))
            f.close()

        fullPath = os.path.join(dirName, fileName)
        self.lastImage = fullPath
        self.lastDir = dirName
        self.lastID = id
        
        return fullPath

    def lastImageNum(self):
        """ Return the last image number taken, or 'nan'."""

        if self.lastID == None:
            return 'nan'
        else:
            return "%04d" % (self.lastID)

    def cidForCmd(self, cmd):
        return "%s.%s" % (cmd.fullname, self.name)

