__all__ = ['GCamera']

""" GCamera.py -- base guide camera controllers.

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

class GCamera(object):
    def __init__(self, name, path, ccdSize, **argv):
        """ Create a GCamera instance.

        Args:
             name        - a unique, human-readable name.
             path        - a root path for image files. We add a per-day subdirectory
             ccdSize     - [x, y] - the size of the unbinned fullframe CCD.
        """
        
        self.name = name
        self.nameChar = name[0]
        
        # Basic sanity checks _now_
        #
        if not os.path.isdir(path):
            raise RuntimeError("path given to %s is not a directory: %s" % (name, path))

        self.ccdSize = ccdSize
        self.path = path

        self.lastImage = None
        self.lastDir = None
        self.lastID = None

        CPL.log("GCamera", "after init: %s" % (self))
        
    def __str__(self):
        return "GCamera(name=%s, ccdSize=%s, path=%s)" % (self.name, self.ccdSize, self.path)
    
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

    def writeFITS(self, cmd, frame, d):
        """ Write an image to a new FITS file.

        Args:
            cmd    - the controlling Command
            frame  - the ImageFrame
            d   - dictionary including:
                     type:     FITS IMAGETYP
                     iTime:    integration time
                     filename: the given filename, or None
                     data:     the image data as a string, or None if saved to a file.

        """

        filename = self._getFilename()
        f = file(filename, 'w')
        os.chmod(filename, 0644)
        
        basename = os.path.basename(filename)

        binning = frame.frameBinning
        corner, size = frame.imgFrameAsCornerAndSize()
        
        # cmd.warn('debug=%s' % (CPL.qstr("writeFITS frame=%s" % (frame))))

        cards = ["%-80s" % ('SIMPLE  = T'),
                 "%-80s" % ('BITPIX  = 16'),
                 "%-80s" % ('NAXIS   = 2'),
                 "%-80s" % ('NAXIS1  = %d' % (size[0])),
                 "%-80s" % ('NAXIS2  = %d' % (size[1])),
                 "%-80s" % ("INSTRUME= '%s'" % self.name),
                 "%-80s" % ('BSCALE  = 1.0'),
                 "%-80s" % ('BZERO   = 32768.0'),
                 "%-80s" % ("IMAGETYP= '%s'" % d['type']),
                 "%-80s" % ('EXPTIME = %0.2f' % d['iTime']),
                 "%-80s" % ('CCDTEMP = %0.1f' % (self.getCCDTemp())),
                 "%-80s" % ("FILENAME= '%s'" % (basename)),
                 "%-80s" % ("FULLX   = %d" % (self.ccdSize[0])),
                 "%-80s" % ("FULLY   = %d" % (self.ccdSize[1])),
                 "%-80s" % ("BEGX    = %d" % (corner[0])),
                 "%-80s" % ("BEGY    = %d" % (corner[1])),
                 "%-80s" % ("BINX    = %d" % (binning[0])),
                 "%-80s" % ("BINY    = %d" % (binning[1])),
                 "%-80s" % ('END')]

        # Write out all our header cards
        for c in cards:
            f.write(c)

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
    
