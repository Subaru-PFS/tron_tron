__all__ = ['getDayDirName',
           'getQuarterName']

import time

localTZ = 6 * 3600

def getDayDirName(t=None):
    """ Return a per-day directory name.

    Returns:
         - a string of the form "UT041219"

    The rule is a bit odd:
       - the night starts at local noon
       - 
    """

    if t == None:
        t = time.time()
    localNow = t - localTZ

    localNowPlus12H = localNow + (12 * 3600)
    dateString = time.strftime("UT%y%m%d", time.gmtime(localNowPlus12H))

    return dateString

def getQuarterName(t=None):
    """ Return the current quarter name.

    Returns:
      - a string of the form 'Q3'
    """

    if t == None:
        t = time.time()
    localNow = t - localTZ

    # Uck. We do _not_ want the last night in the quarter to be assigned to the next quarter.
    # So use _today_'s date to determine the quarter.
    localNowMinus12H = localNow - (12 * 3600)
    month = time.gmtime(localNowMinus12H)[1]

    return "Q%d" % ((month + 2) / 3)

def _test():
    now = time.time()
    for h in range(24):
        testNow = now + h * 3600
        print getDayDirName(t=testNow)

if __name__ == "__main__":
    _test()
    
