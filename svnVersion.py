#!/usr/bin/env python

import commands
import os
import re
import urllib
import sys

# A dictionary with all known keywords. We only use the HeadURL keyword, but it could be
# useful to have them all. Note that the Date/Revision values are rarely accurate, since
# they apply only to this file. 
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
    

def svnRevision(dir=None):
    """ Return the revision number as a string. Or an empty string.
    Since the Revison keyword only tracks the revision of this file, we
    need to use the svnversion program output. The annoying thing there is
    deciding which file/path to examine. """

    if dir == None: dir = '.'

    status, version = commands.getstatusoutput('svnversion %s' % (dir))
    if status != 0:
        return "unknown"
    return version
    
def svnLabels(dir=None):
    """ Return what we can figure out about the identity of the 

    The directory passed in _MUST_ be the top level directory of the project.

    Returns:
      - a string describing the 'type' of the revision.
          One of: ('trunk', 'tag', 'branch', 'unknown')
      - the branch or tag name. Can be 'trunk' or 'unknown'
      - the revision string. Can be 'unknown'

       For development on the trunk:
          ('trunk', 'trunk', '299M')
       For development on a branch:
          ('branch', 'PR89', '201')
       For an exported tag:
          ('tag', 'v1_42', 'exported')

    """

    # Fetch the revision number(s).
    revision = svnRevision(dir)

    fullURL = stripKeyword(svnInfo['HeadURL'])
    if not fullURL:
        return 'unknown','unknown', revision, 'unknown'
    
    # Try to pull the tag apart a bit.
    #
    dummy, url = urllib.splittype(fullURL)
    host, fullPath = urllib.splithost(url)

    # This is ambiguous and stupid.
    # Assume we are in the top directory.
    parts = fullPath.split('/')
    if len(parts) < 2:
        return 'unknown', 'unknown', revision, fullURL

    ourDir, ourName = parts[-2], parts[-1]
    if ourDir == 'trunk':
        return 'trunk', 'trunk', revision, fullURL

    # Double check for conventional "/tags/" dir name. We could, I
    # suppose, be informative if this fails, but it is all gross
    # enough to want to skip.
    if len(parts) < 3:
        return 'unknown', 'unknown', revision, fullURL

    baseDir = parts[-3]
    if baseDir == 'tags':
        return 'tag', ourDir, revision, fullURL
    elif baseDir == 'branches':
        return 'branch', ourDir, revision, fullURL
    else:
        return 'unknown', 'unknown', revision, fullURL

def svnName(dir='.'):
    variant, name, revision, url = svnLabels(dir=dir)

    if variant == 'tag' and revision == 'exported':
        return 'Tag: %s' % (name)
    else:
        return 'BadTag: %r %r %r %r' % (variant, name, revision, url)

def svnTagOrRevision(dir='.'):
    variant, name, revision, url = svnLabels(dir=dir)

    if variant == 'tag' and revision == 'exported':
        return 'Tag: %s' % (name)
    else:
        return 'Tag: UNTAGGED_REVISION %s' % (revision)

def main():
    if len(sys.argv) > 1:
        dir = sys.argv[1]
    else:
        dir = None
        
    print "svnName: \n", svnName(dir=dir)
    print "svnTagOrRevision: \n", svnTagOrRevision(dir=dir)

if __name__ == "__main__":
    main()
