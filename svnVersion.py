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
    

def svnRevision(dir):
    """ Return the revision number, as a string. Or an empty string.
    Since the Revison keyword only track the revision of this file, we
    need to use the svnversion program output. The trick thing there is
    deciding which file/path to examine. """

    import commands

    status, version = commands.getstatusoutput('svnversion %s' % (dir))
    if status != 0:
        return "unknown"
    return version
    
def svnTagOrRevision(dir='.'):
    """ If this is a tagged version, return a string indicating the tag name. Otherwise
    return a string indicating the revision number.

    The directory passed in _MUST_ be the top level directory of the project.
    """

    revision = svnRevision(dir)
    if revision not in ('unknown', 'exported'):
        return "UNTAGGED_REVISION: %s" % (revision)

    fullURL = stripKeyword(svnInfo['HeadURL'])
    if not fullURL:
        return "NO_TAG_OR_REVISION"

    # Try to pull the tag apart a bit.
    #
    dummy, url = urllib.splittype(fullURL)
    host, fullPath = urllib.splithost(url)

    # This is ambigiuous and stupid.
    # Assume we are in the top directory.
    parts = fullPath.split('/')
    if len(parts) < 2:
        return "BADTAG_REVISION: %s" % (fullURL)

    ourDir, ourName = parts[-2], parts[-1]
    if ourDir == 'trunk':
        return "UNTAGGED_REVISION: %s" % (fullURL)

    # Double check for conventional "/tags/" dir name. We could, I
    # suppose, be informative if this fails, but it is all gross
    # enough to want to skip.
    if len(parts) < 3:
        return "BADTAG_REVISION: %s" % (fullURL)
    baseDir = parts[-3]
    if baseDir == 'tags':
        return "Tag: %s" % (ourDir)
    else:
        return "BADTAG_REVISION: %s" % (fullURL)

def test():
    print svnTagOrRevision()
    print "Revision: %s" % svnRevision()

if __name__ == "__main__":
    test()
    
        
    

    
