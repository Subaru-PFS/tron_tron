__all__ = ['centroid',
           'findstars',
           'genStarKey',
           'genStarKeys']

import pyfits

import CPL
import PyGuide
import GuideFrame

class StarInfo(object):
    pass

def xy2ij(pos):
    """ Swap between (x,y) and image(i,j). """
    return pos[1], pos[0]

def ij2xy(pos):
    """ Swap between image(i,j) and (x,y). """
    return pos[1], pos[0]

def findstars(cmd, filename, mask, frame, tweaks, cnt=10):
    """ Run PyGuide.findstars on the given file

    Args:
        cmd       - a controlling Command, or None
        filename  - an absolute pathname of a FITS file.
        mask      - a GuiderMask
        frame     - a GuiderFrame for us to molest.
        tweak     - a dictionary of tweaks. We use ()

    Returns:
        - the PyGuide.findstars isSat flag
        - a list of StarInfos

    """
    
    fits = pyfits.open(filename)
    img = fits[0].data
    header = fits[0].header
    fits.close()

    frame.setImageFromFITSHeader(header)
    maskbits = mask.getMaskForGFrame(cmd, frame)
    
    try:
        isSat, stars = PyGuide.findStars(
            img, maskbits,
            tweaks['bias'],
            tweaks['readNoise'],
            tweaks['ccdGain'],
            dataCut = tweaks['starThresh'],
            verbosity=0
            )
    except Exception, e:
        cmd.warn('debug=%s' % (CPL.qstr(e)))
        isSat = False
        stars = []
        raise

    if cmd and isSat:
        cmd.warn('findstarsSaturated')

    starList = []
    i=1
    for star in stars:
        CPL.log('star', 'star=%s' % (star))

        ctr = ij2xy(star.ctr)
        err = ij2xy(star.err)

        try:
            shape = PyGuide.starShape(img,
                                      maskbits,
                                      star.ctr)
            fwhm = shape.fwhm
            chiSq = shape.chiSq
            bkgnd = shape.bkgnd
            ampl = shape.ampl
        except:
            cmd.warn("findstarsTxt=%s" % (CPL.qstr("starShape failed: %s" % e)))
            fwhm = 0.0        # nan does not work.
            chiSq = 0.0
            bkgnd = 0.0
            ampl = 0.0

        s = StarInfo()
        s.ctr = ctr
        s.err = err
        s.fwhm = (fwhm, fwhm)
        s.angle = 0.0
        s.counts = star.counts
        s.bkgnd = bkgnd
        s.ampl = ampl
        s.chiSq = chiSq
        s.asymm = star.asymm
        
        starList.append(s)
            
        i += 1
        if i >= cnt:
            break

    del img
    del mask
    
    return isSat, starList

def centroid(cmd, filename, mask, frame, seed, tweaks):
    """ Run PyGuide.findstars on the given file

    Args:
        cmd       - a controlling Command, or None
        filename  - an absolute pathname of a FITS file.
        mask      - a GuiderMask
        frame     - a GuiderFrame for us to molest.
        seed      - the initial position.
        tweak     - a dictionary of tweaks. We use ()

    Returns:
        - one StarInfo, or None

    """
    
    fits = pyfits.open(filename)
    img = fits[0].data
    header = fits[0].header
    fits.close()

    frame.setImageFromFITSHeader(header)
    maskbits = mask.getMaskForGFrame(cmd, frame)

    cSeed = xy2ij(seed)
    try:
        star = PyGuide.centroid(
            img, maskbits,
            cSeed,
            tweaks['radius'],
            tweaks['bias'],
            tweaks['readNoise'],
            tweaks['ccdGain']
            )
    except RuntimeError, e:
        cmd.warn('centroidTxt=%s' % (CPL.qstr(e.args[0])))
        return None
    except Exception, e:
        cmd.warn('debug=%s' % (CPL.qstr(e)))
        raise

    ctr = ij2xy(star.ctr)
    err = ij2xy(star.err)

    try:
        shape = PyGuide.starShape(img,
                                  maskbits,
                                  star.ctr)
        fwhm = shape.fwhm
        chiSq = shape.chiSq
        bkgnd = shape.bkgnd
        ampl = shape.ampl
    except Exception, e:
        cmd.warn("debug=%s" % (CPL.qstr("starShape failed: %s" % e)))
        fwhm = 0.0        # nan does not work.
        chiSq = 0.0
        bkgnd = 0.0
        ampl = 0.0

    # Put _eveything into a single structure
    s = StarInfo()
    s.ctr = ctr
    s.err = err
    s.fwhm = (fwhm, fwhm)
    s.angle = 0.0
    s.counts = star.counts
    s.bkgnd = bkgnd
    s.ampl = ampl
    s.chiSq = chiSq
    s.asymm = star.asymm
    
    del img
    del mask
    
    return s

def genStarKeys(cmd, stars, keyName='star'):
    """ Generate the canonical star keys.

    Args:
       cmd     - the Command to respond to.
       stars   - a list of StarInfos
       keyname ? the key name to generate. Defaults to 'star'
    """

    i = 1
    for s in stars:
        genStarKey(cmd, s, i, keyName=keyName)
        i += 1
        
def genStarKey(cmd, s, idx=0, keyName='star'):
    """ Generate the canonical star keys.

    Args:
        cmd     - the Command to respond to.
        idx     - the index of the star in the star list.
        s       - the StarInfo
        keyName ? the key name to use. Defaults to 'star'
    """

    cmd.respond('%s=%d,%0.3f,%0.3f, %0.3f,%0.3f,%0.3f, %0.3f,%0.3f,%0.2f,%0.3f, %0.1f,%0.1f,%0.1f' % \
                (keyName, idx,
                 s.ctr[0], s.ctr[1],
                 s.err[0], s.err[1],
                 s.asymm,
                 s.fwhm[0], s.fwhm[1], s.angle,
                 s.chiSq,
                 s.counts, s.bkgnd, s.ampl))

    
    
