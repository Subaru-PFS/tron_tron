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

def dither(expTime, cnt, offsetFunc, *args):
    """ Run a simple dither script.

    Args:
       expTime    - how long to integrate at each position.
       cnt        - how many integrations to take at each position.
       offsetFunc - the dithering (Python) function. Must return a list of TCC offset commands.
       *args      - a variable number of arguments for the dithering function.
       
    """

    for offset in offsetFunc(*args):
        print "exposing (%0.2f sec)..." % (expTime)
        # expose("inst=grim object n=%d time=%f", (cnt, expTime))
        grim('integrate: %d' % int(expTime * 1000))
        
        print "offsetting (%s)..." % (offset)
        tcc(offset)


if __name__ == "__main__":
    # Boilerplate. Connect to the hub and set up communications
    run()

    # Must authenticate in here rather than lie.
    call('hub', 'setProgram APO')
    call('hub', 'setUsername ditherTest')

    # Call our dither script.
    for r in range(10):
        dither(2, 1, square, 10)


