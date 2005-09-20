#!/usr/bin/env python

import os
import re
import urllib

svnInfo = { 'Date' : '$Date$',
            'Revision' : '$Revision$',
            'Author' : '$Author$',
            'HeadURL' : '$HeadURL$',
            'Id' : '$Id$'
            }

def stripKeyword(s):
    """ Remove the svn keyword goo from a string.

    Args:
        s          : a full svn keyword (e.g. '$Revision$')

    Returns:
        - the content of the keyword (e.g. '124')
    """

    m = re.match('^\$[^:]+: (.*) \$$', s)
    if not m:
        return None

    return m.group(1)
    

def svnRevision():
    """ Return the revision number, as a string. Or an empty string. """

    return stripKeyword(svnInfo['Revision'])
                       
def svnTagOrRevision():
    """ If this is a tagged version, return a string indicating the tag name. Otherwise
    return a string indicating the revision number.
    """

    fullURL = stripKeyword(svnInfo['HeadURL'])
    if not fullURL:
        return "UNTAGGED_REVISION: %s" % (svnRevision())

    # Try to pull the tag apart a bit.
    #
    dummy, url = urllib.splittype(fullURL)
    host, fullPath = urllib.splithost(url)

    # This is ambigiuous and stupid.
    # Assume we are in the top directory.
    parts = fullPath.split('/')
    if len(parts) < 2:
        return "BADTAG_REVISION: %s" % (svnRevision())

    ourDir, ourName = parts[-2], parts[-1]
    if ourDir == 'trunk':
        return "UNTAGGED_REVISION: %s" % (svnRevision())

    # Double check for conventional "/tags/" dir name. We could, I
    # suppose, be informative if this fails, but it is all gross
    # enough to want to skip.
    if len(parts) < 3:
        return "BADTAG_REVISION: %s" % (svnRevision())
    baseDir = parts[-3]
    if baseDir == 'tags':
        return "Tag: %s" % (ourDir)
    else:
        return "BADTAG_REVISION: %s" % (svnRevision())

def test():
    print svnTagOrRevision()

if __name__ == "__main__":
    test()
    
        
    

    
