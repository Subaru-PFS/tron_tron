__all__ = ['GuiderMask']

import os
import time

import CPL
import pyfits

class GuiderMask(object):
    def __init__(self, cmd, baseFile, maskDir):
        """ Load ourselves from baseFile, which must be a full-frame, unbinned
        image.

        Args:
           cmd        - the current command
           baseFile   - absolute path of full-frame, unbinned image
           maskDir    - where to put the temporary mask files.
        """

        self.baseFile = baseFile
        self.maskDir = maskDir
        self.binning = [0,0]
        self.offset = [-1,-1]
        self.size = [0,0]

        # Create scratch mask directory
        if not os.path.isdir(self.maskDir):
            os.makedirs(self.maskDir, mode=0755)
            
        self.fullSize = self.getImgSize(self.baseFile)

        # We could cache all recent subframes, or we could just cache the last one.
        # I'll wager that the last one is good enough,
        #
        self.cachedMask = None
        self.getMaskForFrame(None, [1,1])

        if cmd:
            self.statusCmd(cmd, doFinish=False)

    def getBaseDir(self):
        """ Return the current image directory for all raw and synthesized images. """

        dateName = CPL.getDateDirName()
        return os.path.join(self.imagePath, dateName)
    
    def statusCmd(self, cmd, doFinish=True):
        """ Generate our keys.
        """
            
        cmd.respond('baseMask=%s' % (CPL.qstr(self.baseFile)))
        cmd.respond('maskFile=%s' % (CPL.qstr(self.maskFile)))

        if doFinish:
            cmd.finish()
        
    def getImgSize(self, fname):
        """ Return the size of the given FITS file's data. """

        f = pyfits.open(fname)
        im = f[0].data
        f.close()

        return list(im.getshape())
    
    def getMaskForGFrame(self, cmd, gframe):
        """ Return the mask adjusted for a given GuiderFrame. """

        return self.getMaskForFrame(cmd, *gframe.imgFrame())
    
    def getMaskForFrame(self, cmd, binning, offset=[0,0], size=None):
        """ Return the mask adjusted for a given subframe and binning.
        Caches the current mask.

        Args:
           cmd        - the controlling Command. We alert if the mask has been changed
           binning    - [x,y] (x should be == y).
           offset     - desired subframe corner [x0, y0], in binned pixels
           size       - desired subframe size [w, h], in binned pixels
           
        Returns:
           a Numeric mask.
        """

        if size == None:
            size = [self.fullSize[0] / binning[0] - offset[0],
                    self.fullSize[1] / binning[1] - offset[1]]

        # Make sure that our args will a) compare nicely and format nicely for IDL.
        size = list(size)
        offset = list(offset)
        binning = list(binning)
        
        if self.cachedMask != None and \
               binning == self.binning and \
               offset == self.offset and \
               size == self.size:
            return self.cachedMask

        # Call an external IDL routine which rebins for us. The ugly secret
        # which this papers over is that Numeric stinks.
        #
        basedir, basefile = os.path.split(self.baseFile)
        basename, ext = os.path.splitext(basefile)
        serial = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        newFile = os.path.join(self.maskDir,
                               "%s-%s%s" % (basename, serial, ext))

        IDLcmd = "echo \"fsubframe, '%s', '%s', %s, %s, %s\" | idl" % (self.baseFile, newFile,
                                                                       offset, size,
                                                                       binning)
        CPL.log('IDLcmd', IDLcmd)
        
        # MUST run this so that errors get to us! FIXME!
        ret = os.system(IDLcmd)
        if ret != 0:
            raise RuntimeError("could not reshape the mask file by running '%s'" % (IDLcmd))
        
        f = pyfits.open(newFile)
        im = f[0].data
        f.close()
        
        self.maskFile = newFile
        self.cachedMask = im <= 0
        self.binning = binning
        self.size = size
        self.offset = offset

        if cmd:
            cmd.respond('maskFile=%s' % (CPL.qstr(newFile)))
            
        return self.cachedMask

if __name__ == "__main__":
    os.environ['IDL_PATH'] = '/export/images/keep/masks:+/usr/local/rsi/local/goddard'
    m = GuiderMask("/export/images/keep/masks/na2.fits", [3,3])

    mask = m.getMaskForBinning([3,3])
    print mask.size()

    mask = m.getMaskForBinning([1,1])
    print mask.size()

    mask = m.getMaskForBinning([3,3])
    print mask.size()

    mask = m.getMaskForBinning([3,3])
    print mask.size()

    
