__all__ = ['GuiderMask']

import os
import pyfits

class GuiderMask(object):
    def __init__(self, baseFile, maskDir):
        """ Load ourselves from baseFile, which must be a full-frame, unbinned
        image.
        """

        self.baseFile = baseFile
        self.maskDir = maskDir
        self.binning = [0,0]
        self.offset = [0,0]
        self.size = [0,0]

        # We could cache all recent subframes, or we could just cache the last one.
        # I'll wager that the last one is good enough,
        #
        self.maskFile = None
        self.cachedMask = None
        
    def XXXXXgetMaskForBinning(self, newBinning):
        """ Return the mask adjusted for the given binning. Caches the current mask.

        Args:
           newBinning    - [x,y] (x should be == y).

        Returns:
           a new mask.
        """

        if newBinning == self.binning:
            return self.cachedMask

        # Call an external IDL routine which rebins for us. The ugly secret
        # which this papers over is that Numeric stinks.
        #
        basename, ext = os.path.splitext(self.baseFile)
        newFile = "%s-%dx%s%s" % (basename, newBinning[0], newBinning[1], ext)

        cmd = "echo \"frebin_mask, '%s', '%s', %s\" | idl" % (self.baseFile,
                                                              newFile,
                                                              newBinning)

        ret = os.system(cmd)
        if ret != 0:
            raise RuntimeError("could not rebin the mask file by running '%s'" % (cmd))
        
        f = pyfits.open(newFile)
        im = f[0].data
        f.close()
        
        self.cachedMask = im <= 0
        self.binning = newBinning

        return self.cachedMask

    def getMaskForFrame(self, binning, offset, size):
        """ Return the mask adjusted for a given subframe and binning.
        Caches the current mask.

        Args:
           binning    - [x,y] (x should be == y).
           offset     - [x0, y0]
           size       [w, h]
           
        Returns:
           a new mask.
        """

        if self.cachedMask and \
               binning == self.binning and \
               offset == self.offset and \
               size == self.size:
            return self.cachedMask

        # Call an external IDL routine which rebins for us. The ugly secret
        # which this papers over is that Numeric stinks.
        #
        basename, ext = os.path.splitext(self.baseFile)
        newFile = "%s-%dx%d%s" % (basename, newBinning[0], newBinning[1],
                                  ext)

        cmd = "echo \"frebin_mask, '%s', '%s', %s\" | idl" % (self.baseFile,
                                                              newFile,
                                                              newBinning)

        ret = os.system(cmd)
        if ret != 0:
            raise RuntimeError("could not rebin the mask file by running '%s'" % (cmd))
        
        f = pyfits.open(newFile)
        im = f[0].data
        f.close()
        
        self.cachedMask = im <= 0
        self.binning = newBinning

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

    
