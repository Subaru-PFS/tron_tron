__all__ = ['centroid',
           'findstars',
           'genStarKey',
           'genStarKeys']

import sys

import numarray
import pyfits

import CPL
import PyGuide
import GuideFrame

class StarInfo(object):
    def __str__(self):
        return "Star(ctr=%r err=%r fwhm=%r)" % (self.ctr, self.err, self.fwhm)

    def copy(self):
        """ Return a shallow copy of ourselves. """
        
        ns = StarInfo()
        for k, v in self.__dict__.iteritems():
            ns.__dict__[k] = v

        return ns

def findstars(cmd, imgFile, maskFile, frame, tweaks, radius=None, cnt=10):
    """ Run PyGuide.findstars on the given file

    Args:
        cmd       - a controlling Command, or None
        imgFile   - an absolute pathname of a FITS file.
        maskFile  - an absolute pathname of a mask file.
        frame     - a GuiderFrame for us to molest.
        tweaks    - a dictionary of tweaks.
        cnt       ? the number of stars to return. 

    Returns:
        - a list of StarInfos, in full CCD coordinates
    """

    if tweaks.has_key('cnt'):
        cnt = tweaks['cnt']
        
    fits = pyfits.open(imgFile)
    img = fits[0].data
    min = img.min()
    max = img.max()
    if min < 0 or max > 65536:
        cmd.warn('text="bad pixel values for findstars: %0.1f .. %0.1f"' % (min, max))
    #img = img.astype('u2')
    header = fits[0].header
    fits.close()
    del fits
    
    if not frame:
        frame = GuideFrame.ImageFrame(img.shape)
    frame.setImageFromFITSHeader(header)

    # Prep for optional ds9 output
    ds9 = tweaks.get('ds9', False)

    if maskFile:
        fits = pyfits.open(maskFile)
        maskbits = fits[0].data
        maskbits = maskbits < 0.01
        maskbits = maskbits.astype('u2')
        fits.close()
        del fits
    else:
        maskbits = img * 0 + 1
        cmd.warn('text="no mask file available to findstars"')

    CPL.log('findstars', 'tweaks=%s' % (tweaks))
    
    thresh = tweaks['thresh']
    if thresh < 1.5:
        cmd.warn('text=%s' % (CPL.qstr("adjusted too small threshold (%0.2f) up to 1.5" % (thresh,))))
        thresh = 1.5

    ccdInfo = PyGuide.CCDInfo(tweaks['bias'], tweaks['readNoise'], int(tweaks['ccdGain']))

    CPL.log('findstars', 'imgFile=%s, maskFile=%s, tweaks=%s' % (imgFile, maskFile, tweaks))
    
    try:
        res = PyGuide.findStars(
            img, maskbits, ccdInfo,
            thresh = thresh,
            radMult = tweaks['radMult'],
            rad=None,
            verbosity=0,
            doDS9=ds9
            )
        stars, imstats = res[:2]
    except Exception, e:
        cmd.warn('debug=%s' % (CPL.qstr(e)))
        CPL.tback('findstars', e)
        stars = []
        raise

    starList = []
    i=1
    for star in stars:
        CPL.log('star', 'star=%s' % (star))

        if not star.isOK:
            cmd.warn('text="ignoring object at (%0.1f,%0.1f): %s"' % \
                     (star.xyCtr[0], star.xyCtr[1], star.msgStr))
            continue
        
        #if star.rad > 2 * tweaks['cradius']:
        #    cmd.warn('text="ignoring huge object (rad=%0.1f) at (%0.1f,%0.1f)"' % \
        #             (star.rad,
        #              star.xyCtr[0], star.xyCtr[1]))
        #    continue

        if star.nSat:
            if star.nSat >= 5:
                cmd.warn('text="ignoring object at (%0.1f,%0.1f): %d saturated pixels"' % \
                         (star.xyCtr[0], star.xyCtr[1], star.nSat))
                continue
            cmd.warn('text="object at (%0.1f,%0.1f): %d has saturated pixels"' % \
                     (star.xyCtr[0], star.xyCtr[1], star.nSat))
        
        s = starshape(cmd, frame, img, maskbits, star, tweaks)
        if not s:
            continue
        starList.append(s)
            
        i += 1
        if i >= cnt:
            break

    del img
    del maskbits
    
    return starList

def centroid(cmd, imgFile, maskFile, frame, seed, tweaks, xxx=None):
    """ Run PyGuide.findstars on the given file

    Args:
        cmd       - a controlling Command, or None
        imgFile   - an absolute pathname of a FITS file.
        maskFile  - an absolute pathname of a mask file.
        frame     - a GuiderFrame for us to molest.
        seed      - the initial [X,Y] position, in full CCD coordinates
        tweak     - a dictionary of tweaks. We use ()

    Returns:
        - one StarInfo, or None. In full CCD coordinates.

    """

    if xxx:
        xxx(cmd, "centroid_1")
    fits = pyfits.open(imgFile)
    img = fits[0].data
    min = img.min()
    max = img.max()
    if min < 0 or max > 65536:
        cmd.warn('text="bad pixel values for findstars: %0.1f .. %0.1f"' % (min, max))
    #img = img.astype('u2')
    header = fits[0].header
    fits.close()
    del fits

    if xxx:
        xxx(cmd, "centroid_2")

    # Prep for optional ds9 output
    ds9 = tweaks.get('ds9', False)

    if not frame:
        frame = GuideFrame.ImageFrame(img.shape)
    frame.setImageFromFITSHeader(header)

    if xxx:
        xxx(cmd, "centroid_3")

    if maskFile:
        fits = pyfits.open(maskFile)
        maskbits = fits[0].data
        maskbits = maskbits < 0.01
        maskbits = maskbits.astype('b')
        fits.close()
        del fits
    else:
        maskbits = img * 0 + 1
        cmd.warn('text="no mask file available to centroid"')

    if xxx:
        xxx(cmd, "centroid_4")

    thresh = tweaks['thresh']
    if thresh < 1.5:
        cmd.warn('text=%s' % (CPL.qstr("adjusted too small threshold (%0.2f) up to 1.5" % (thresh,))))
        thresh = 1.5

    ccdInfo = PyGuide.CCDInfo(tweaks['bias'], tweaks['readNoise'], int(tweaks['ccdGain']))
    
    #cmd.warn('debug=%s' % (CPL.qstr("calling centroid file=%s, frame=%s, seed=%s" % \
    #                                (imgFile, frame, seed))))
    try:
        star = PyGuide.centroid(
            img, maskbits,
            seed,
            tweaks['cradius'],
            ccdInfo,
            thresh=thresh,
            doDS9=ds9
            )
    except RuntimeError, e:
        cmd.warn('text=%s' % (CPL.qstr(e.args[0])))
        return None
    except Exception, e:
        CPL.tback('centroid', e)
        cmd.warn('text=%s' % (CPL.qstr(e)))
        raise

    if xxx:
        xxx(cmd, "centroid_5")

    if not star.isOK:
        cmd.warn('debug="ignoring object at (%0.1f,%0.1f): %s"' % \
                 (seed[0], seed[1], star.msgStr))
        return None
        
    if star.nSat:
        if star.nSat >=4:
            cmd.warn('text="ignoring object at (%0.1f,%0.1f): %d saturated pixels"' % \
                     (star.xyCtr[0], star.xyCtr[1], star.nSat))
            return None
        if star.nSat >=4:
            cmd.warn('text="object at (%0.1f,%0.1f): %d has saturated pixels"' % \
                     (star.xyCtr[0], star.xyCtr[1], star.nSat))
        
    s = starshape(cmd, frame, img, maskbits, star, tweaks)
    
    del img
    del maskbits

    if xxx:
        xxx(cmd, "centroid_6")
    
    return s

def starshape(cmd, frame, img, maskbits, star, tweaks):
    """ Generate a StarInfo structure which contains everything about a star.

    Args:
        cmd       - the controlling Command
        frame     - an ImageFrame
        img       - a 2d numarray image
        maskbits  - ditto
        star      - PyGuide centroid info.
    """

    # cmd.warn('debug="ss img refs 1 = %d"' % (sys.getrefcount(img)))

    try:
        shape = PyGuide.starShape(img, maskbits,
                                  star.xyCtr,
                                  star.rad)
        fwhm = shape.fwhm
        chiSq = shape.chiSq
        bkgnd = shape.bkgnd
        ampl = shape.ampl

        #if ampl < 5:
        #    raise RuntimeError('amplitude of fit too low (%0.2f)' % (ampl))
    except Exception, e:
        cmd.warn("debug=%s" % \
                 (CPL.qstr("starShape failed, vetoing star at %0.2f,%0.2f: %s" % \
                           (star.xyCtr[0], star.xyCtr[1], e))))
        shape = None
        fwhm = 0.0
        chiSq = 0.0
        bkgnd = 0.0
        ampl = 0.0
        return None

    if shape and not shape.isOK:
        cmd.warn('text="starShape failed on (%0.1f, %0.1f): %s"' % \
                 (star.xyCtr[0], star.xyCtr[1], shape.msgStr))
        fwhm = 0.0
        chiSq = 0.0
        bkgnd = 0.0
        ampl = 0.0
        return None
        
    # Put _eveything into a single structure
    s = StarInfo()
    s.ctr = star.xyCtr
    s.err = star.xyErr
    s.fwhm = (fwhm, fwhm)
    s.angle = 0.0
    s.radius = star.rad
    s.counts = star.counts
    s.pixels = star.pix
    s.asymm = star.asymm

    s.bkgnd = bkgnd
    s.ampl = ampl
    s.chiSq = chiSq

    return s

def imgPos2CCDXY(pos, frame):
    """ Convert an image position to a CCD StarInfo.

    Args:
         pos     - an (x,y) pair in image coordinates
         frame   - a CCD/image coordinate frame

    Returns
        - a StarInfo 
    """

    s = StarInfo()
    s.ctr = pos
    s.err = (0.0, 0.0)
    s.fwhm = (0.0, 0.0)

    return star2CCDXY(s, frame)


def star2CCDXY(star, frame):
    """ Convert all convertable star coordinates from image to CCD coordinates

    Args:
        star      - a StarInfo
        frame     - a CCD/image coordinate frame.

    Returns:
        - a new StarInfo
    """

    CCDstar = star.copy()

    binning = frame.frameBinning

    ctr = frame.imgXY2ccdXY(star.ctr)
    err = star.err[0] * binning[0], \
          star.err[1] * binning[1]           
    fwhm = star.fwhm[0] * binning[0], \
           star.fwhm[1] * binning[1]

    CCDstar.ctr = ctr
    CCDstar.err = err
    CCDstar.fwhm = fwhm

    return CCDstar

def genStarKeys(cmd, stars, keyName='star', caller='x', cnt=None):
    """ Generate the canonical star keys.

    Args:
       cmd     - the Command to respond to.
       stars   - a list of StarInfos
       keyname ? the key name to generate. Defaults to 'star'
       caller  ? an indicator of the caller's identity.
       cnt     ? limit the number of stars output to the given number
    """

    i = 1
    for s in stars:
        genStarKey(cmd, s, i, keyName=keyName, caller=caller)

        if cnt and i >= cnt:
            break
        i += 1
        
def genStarKey(cmd, s, idx=1, keyName='star', caller='x'):
    """ Generate the canonical star keys.

    Args:
        cmd     - the Command to respond to.
        idx     - the index of the star in the star list.
        s       - the StarInfo
        keyName ? the key name to use. Defaults to 'star'
        caller  ? the 'reason' field.
    """

    cmd.respond('%s=%s,%d,%0.2f,%0.2f, %0.2f,%0.2f,%0.2f,%0.2f, %0.2f,%0.2f,%0.2f,%0.2f, %d,%0.1f,%0.1f' % \
                (keyName,
                 CPL.qstr(caller),
                 idx,
                 s.ctr[0], s.ctr[1],
                 s.err[0], s.err[1],
                 s.radius,
                 s.asymm,
                 s.fwhm[0], s.fwhm[1], s.angle,
                 s.chiSq,
                 s.counts, s.bkgnd, s.ampl))

    
    
