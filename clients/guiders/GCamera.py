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

class GCamera(object):
    def __init__(self, name, path, **argv):

        self.name = name
        
        # Basic sanity checks _now_
        #
        if not os.path.isdir(path):
            raise RuntimeError("path given to %s is not a directory: %s" % (name, path))

        self.path = path
        self.exposeCmd = None

        self.lastImage = None
        
    def _getFilename(self):
        """ Return the next available filename.

        We try to not suffer collisions by naming the files with timestamps and
        putting them in per-day directories.

        This is where we create any necessary directories. And we do that expensively,
        by checking for each file whether the right directory exists.

        We want the directories to change at local noon and be named after the
        new day's date. 
        """

        now = time.time()
        localNow = now - time.timezone
        localNowPlus12H = localNow + (12 * 3600)
        
        dateString = time.strftime("UT%y%m%d", time.gmtime(localNowPlus12H))

        dirName = os.path.join(self.path, dateString)
        if not os.path.isdir(dirName):
            os.mkdir(dirName)
            os.chmod(dirName, 0777)

            fileName = "f0001.fits"
            
            # Create the last.image file
            #
            f = open(os.path.join(dirName, "last.image"), "w+")
            f.write('%s\n' % (fileName))
            f.close()
        else:
            # Create the last.image file
            #
            f = open(os.path.join(dirName, "last.image"), "r+")
            lastFileName = f.readline()
            lastID = int(lastFileName[1:5], 10)
            id = lastID + 1

            if id > 9999:
                raise RuntimeError("guider image number in %s is more than 9999." % (dirName))
            
            fileName = "f%04d.fits" % (id)

            f.seek(0,0)
            f.write('%s\n' % (fileName))
            f.close()

        fullPath = os.path.join(dirName, fileName)
        self.lastImage = fullPath
        return fullPath

    def lastImageNum(self):
        """ Return the last image number taken, or 'nan'."""

        return 'nan'

    def cidForCmd(self, cmd):
        return "%s.%s" % (cmd.fullname, self.name)

    def writeFITS(self, cmd, d):
        """ Write an image to a new FITS file.

        Args:
            d   - dictionary including:
                     size:     (width, height)
                     type:     FITS IMAGETYP
                     iTime:    integration time
                     filename: the given filename, or None
                     data:     the image data as a string, or None if saved to a file.

        """

        filename = self._getFilename()
        f = file(filename, 'w')

        w, h = d['size']
        
        cards = ["%-80s" % ('SIMPLE  = T'),
                 "%-80s" % ('BITPIX  = 16'),
                 "%-80s" % ('NAXIS   = 2'),
                 "%-80s" % ('NAXIS1  = %d' % (w)),
                 "%-80s" % ('NAXIS2  = %d' % (h)),
#                 "%-80s" % ("INSTRUME= '%s'" % self.name),
                 "%-80s" % ('BSCALE  = 1.0'),
                 "%-80s" % ('BZERO   = 32768.0'),
                 "%-80s" % ("IMAGETYP= '%s'" % d['type']),
                 "%-80s" % ('EXPTIME = %0.2f' % d['iTime']),
                 "%-80s" % ('CCDTEMP = %0.1f' % (self.getCCDTemp())),
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
        
        cmd.respond('filename="%s"' % (filename))
        
        return filename
    
