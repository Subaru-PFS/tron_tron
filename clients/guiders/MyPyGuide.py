__all__ = ['centroid',
           'findstars',
           'genStarKey',
           'genStarKeys']

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
    
def findstars(cmd, imgFile, maskFile, frame, tweaks, cnt=10):
    """ Run PyGuide.findstars on the given file

    Args:
        cmd       - a controlling Command, or None
        imgFile   - an absolute pathname of a FITS file.
        maskFile  - an absolute pathname of a mask file.
        frame     - a GuiderFrame for us to molest.
        tweaks    - a dictionary of tweaks.
        cnt       ? the number of stars to return. 

    Returns:
        - the PyGuide.findstars isSat flag
        - a list of StarInfos, in full CCD coordinates
    """
    
    fits = pyfits.open(imgFile)
    img = fits[0].data
    header = fits[0].header
    fits.close()

    if not frame:
        frame = GuideFrame.ImageFrame(img.shape)
    frame.setImageFromFITSHeader(header)

    # cmd.warn('debug=%s' % (CPL.qstr(frame)))

    # Prep for optional ds9 output
    ds9 = tweaks.get('ds9', False)


    if maskFile:
        fits = pyfits.open(maskFile)
        maskbits = fits[0].data
        fits.close()
    else:
        maskbits = img * 0 + 1
        cmd.warn('text="no mask file available to findstars"')

    CPL.log('findstars', 'tweaks=%s' % (tweaks))
    
    try:
        res = PyGuide.findStars(
            img, maskbits,
            tweaks['bias'],
            tweaks['readNoise'],
            tweaks['ccdGain'],
            dataCut = tweaks['thresh'],
            radMult = tweaks['radMult'],
            verbosity=0,
            ds9=ds9
            )
        isSat, stars = res[:2]
    except Exception, e:
        cmd.warn('debug=%s' % (CPL.qstr(e)))
        isSat = False
        stars = []
        raise

    if cmd and isSat:
        cmd.warn('text="saturated stars have been ignored."')

    starList = []
    i=1
    for star in stars:
        CPL.log('star', 'star=%s' % (star))

        rad = star.rad
        if rad > tweaks['cradius']:
            rad = tweaks['cradius']
            cmd.warn('debug="trimming predFWHM for starShape from %0.2f to %0.2f"' % (star.rad, rad))
            star.rad = rad
            
        s = starshape(cmd, frame, img, maskbits, star, tweaks)
        if not s:
            continue
        starList.append(s)
            
        i += 1
        if i >= cnt:
            break

    del img
    del maskbits
    
    return isSat, starList

def centroid(cmd, imgFile, maskFile, frame, seed, tweaks):
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
    
    fits = pyfits.open(imgFile)
    img = fits[0].data
    header = fits[0].header
    fits.close()

    # Prep for optional ds9 output
    ds9 = tweaks.get('ds9', False)

    if not frame:
        frame = GuideFrame.ImageFrame(img.shape)
    frame.setImageFromFITSHeader(header)

    if maskFile:
        fits = pyfits.open(maskFile)
        maskbits = fits[0].data
        fits.close()
    else:
        maskbits = img * 0 + 1
        cmd.warn('text="no mask file available to centroid"')

    #cmd.warn('debug=%s' % (CPL.qstr("calling centroid file=%s, frame=%s, seed=%s" % \
    #                                (imgFile, frame, seed))))
    try:
        star = PyGuide.centroid(
            img, maskbits,
            seed,
            tweaks['cradius'],
            tweaks['bias'],
            tweaks['readNoise'],
            tweaks['ccdGain'],
            ds9=ds9
            )
    except RuntimeError, e:
        cmd.warn('text=%s' % (CPL.qstr(e.args[0])))
        return None
    except Exception, e:
        cmd.warn('text=%s' % (CPL.qstr(e)))
        raise

    s = starshape(cmd, frame, img, maskbits, star, tweaks)
    
    del img
    del maskbits
    
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

        
    try:
        shape = PyGuide.starShape(img,
                                  maskbits,
                                  star.xyCtr,
                                  star.rad)
        fwhm = shape.fwhm
        chiSq = shape.chiSq
        bkgnd = shape.bkgnd
        ampl = shape.ampl

        if ampl < 5:
            raise RuntimeError('amplitude of fit too low (%0.2f)' % (ampl))
    except Exception, e:
        cmd.warn("debug=%s" % \
                 (CPL.qstr("starShape failed, vetoing star at %0.2f,%0.2f: %s" % \
                           (star.xyCtr[0], star.xyCtr[1], e))))
        return
    
    # Put _eveything into a single structure
    s = StarInfo()
    s.ctr = star.xyCtr
    s.err = star.xyErr
    s.radius = star.rad
    s.fwhm = (fwhm, fwhm)
    s.angle = 0.0
    s.counts = star.counts
    s.bkgnd = bkgnd
    s.ampl = ampl
    s.chiSq = chiSq
    s.asymm = star.asymm
    
    return s

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

    
    
