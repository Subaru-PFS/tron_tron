__all__ = ['GuiderMask']

import os
import popen2
import sys

import CPL
import pyfits

class GuiderMask(object):
    def __init__(self, cmd, baseFile, name):
        """ Load ourselves from baseFile, which must be a full-frame, unbinned
        image.

        Args:
           cmd        - the current command
           baseFile   - absolute path of full-frame, unbinned image
           name       - our name, used to query the configuration.
        """

        self.name = name
        self.baseFile = baseFile

        if baseFile:
            try:
                self.fullSize = self.getImgSize(self.baseFile)
            except Exception, e:
                if cmd:
                    cmd.warn('text="Cannot load mask file %s"' % (baseFile))
                raise

        # We could cache all recent subframes, or we could just cache the last one.
        # I'll wager that the last one is good enough,
        #
        self.cachedMask = None
        self.cachedFile = ''
        self.frame = None

        if cmd:
            self.statusCmd(cmd, doFinish=False)

    def statusCmd(self, cmd, doFinish=True):
        """ Generate our keys.
        """
            
        cmd.respond('maskFile=%s' % (CPL.qstr(self.baseFile)))

        if doFinish:
            cmd.finish()
        
    def getImgSize(self, fname):
        """ Return the size of the given FITS file's data. """

        f = pyfits.open(fname)
        im = f[0].data
        f.close()

        size = im.getshape()
        del im

        return list(size)

    def runIDLcmd(self, cmd, IDLcmd):
        CPL.log('IDLcmd', IDLcmd)
        
        o = popen2.Popen3(IDLcmd, True)
        ret = o.wait()
        if ret != 0:
            cmd.warn('text="failed to rehape the mask file"')
            
        for l in o.childerr:
            if l.find('IDL Version') == 0:
                continue
            if l.find('Installation number') == 0:
                continue
            if l.find('Licensed for') == 0:
                continue
            if l.find('% Compiled') == 0:
                continue
            if l.strip() == '':
                continue
            
            cmd.warn('IDLdebug=%s' % (CPL.qstr(l)))
        del o
            
        
    def getMaskForFrame(self, cmd, basename, frame):
        """ Return the mask adjusted for a given subframe and binning.
        Caches the current mask.

        Args:
           cmd        - the controlling Command. We alert if the mask has been changed
           basename   - a filename which we use as a template for our output file.
           frame      - an ImageFrame
           
        Returns:
           - a filename
           - a Numeric mask.
        """

        if not self.baseFile:
            return None, None
        
        # cmd.warn('debug=%s' % (CPL.qstr("frame frame=%s, self=%s" % (frame, self))))
        
        # Make sure that our args will a) compare nicely and format nicely for IDL.
        binning, offset, size = frame.imgFrame()
        
        if self.cachedMask != None \
               and frame == self.frame \
               and os.path.dirname(self.cachedFile) == os.path.dirname(basename):

            #cmd.warn('debug="mask refs = %d %d %d"' % (sys.getrefcount(self.cachedMask),
            #                                           sys.getrefcount(self),
            #                                           sys.getrefcount(frame)))

            return self.cachedFile, self.cachedMask
        else:
            CPL.log('GuiderMask', 'debug=%s' % \
                    (CPL.qstr("creating new mask: basename=%s, cachedFile=%s, frame=%s, self.frame=%s, match=%s" % \
                              (basename, self.cachedFile,
                               frame, self.frame, frame == self.frame))))
                                
            
        # Replace the "name" part of the filename with "mask". e.g.
        #   "g0123.fits" -> "mask0123.fits"
        #
        basedir, basefile = os.path.split(basename)
        numIdx = 0
        for i in range(len(basefile)):
            if basefile[i].isdigit():
                numIdx = i
                break
        basefile = "mask" + basefile[numIdx:]
        newFile = os.path.join(basedir, basefile)

        # Call an external IDL routine which rebins for us. The ugly secret
        # which this papers over is that Numeric stinks.
        #
        IDLcmd = "echo \"fsubmask, '%s', '%s', %s, %s, %s\" | idl" % \
                 (self.baseFile, newFile,
                  list(offset),
                  list(size),
                  list(binning))

        self.runIDLcmd(cmd, IDLcmd)
        
        try:
            f = pyfits.open(newFile)
        except Exception, e:
            raise RuntimeError("mask reshaping failed. IDL command: '%s', error: %s" % (IDLcmd, e))
            
        im = f[0].data
        f.close()

        self.cachedFile = newFile
        self.cachedMask = im
        self.frame = frame

        return self.cachedFile, self.cachedMask

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

    
