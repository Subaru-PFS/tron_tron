from client import *

""" Grim dither scripts.
"""

def square(arcsec):
    """ Return the tcc offset instructions describing a square of the given size.

    Args:
        arcsec  - the desired per-quadrant offset, in arcseconds.

    Returns:
        - a list of complete TCC offset commands.

    Notes:
        The position going in is assumed to be in the top-left quadrant.
    """

    degrees = arcsec / 3600.0
    
    offsets = []
    for x, y in (degrees, 0), (0, degrees), (-degrees, 0), (0, -degrees):
        offsets.append("offset bore %0.6f,%0.6f /nocompute" % (x, y))

    return offsets

def dither(expTime, cnt, offsets):
    """ Run a simple dither script.

    Args:
       expTime    - how long to integrate for.
       cnt        - how many integrations to take at each position.
       offsets    - a list off offsets that we expose at.

    We expose first, then offset.
    """

    for offset in offsets:
        print "exposing (%0.2f sec)..." % (expTime)
        expose("inst=grim object n=%d time=%f", (cnt, expTime))
        
        print "offsetting (%s)..." % (offset)
        tcc(offset)


if __name__ == "__main__":
    # Boilerplate. Connect to the hub and set up communications
    run()

    # Call our dither script.
    offsets = square(10)
    for r in range(10):
        dither(2, 1, square, 10)


