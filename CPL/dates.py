__all__ = ['getDayDirName',
           'getQuarterName']

import time

def getDayDirName(t=None):
    """ Return a per-day directory name.

    Returns:
         - a string of the form "UT041219"
    """

    if t == None:
        t = time.time()
    localNow = t - time.timezone

    # Uck. We do _not_ want the last night in the quarter to be assigned to the next quarter.
    # So use _today_'s date to determine the quarter.
    localNowMinus12H = localNow - (12 * 3600)
    monthForQuarter = time.strftime("%m", time.gmtime(localNowMinus12H))

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
    localNow = t - time.timezone

    # Uck. We do _not_ want the last night in the quarter to be assigned to the next quarter.
    # So use _today_'s date to determine the quarter.
    localNowMinus12H = localNow - (12 * 3600)
    month = time.gmtime(localNowMinus12H)[1]

    return "Q%d" % ((month + 2) / 3)

    
