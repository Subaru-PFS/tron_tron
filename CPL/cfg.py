""" A simple configuration manager. Loads python files in a given directory. That's it.
"""

__all__ = ['init', 'get', 'flush']

import os
import sys

from CPL.Exceptions import ICCError

cfgCache = None

def init(path=None, verbose=True):
    """ Initialize the cfg space.
    
    Args:
        path     - the directory inside which all the cfg files are kept.
    """

    global cfgPath
    
    if path == None:
        path = os.environ.get('CONFIG_DIR', None)

    if path == None:
        raise RuntimeError("Cannot initialize configuration module: no path given")
    
    cfgPath = path
    flush()

    if verbose:
        sys.stderr.write("initialized configuration under %s\n" % (cfgPath))
    
def flush():
    """ Clear any existing configuration cache.
    """

    global cfgCache
    
    cfgCache = {}

__nodef = 'no such variable HERE'
def get(space, var, default=__nodef, doFlush=False):
    """ Fetch a configuration value.
    
    Args:
        space     - the namespace to search.
        var       - the name of the variable to get.
        default   ? if set, and var is not in space, return this.
        doFlush   ? if True, reload the config cache.
    """

    if doFlush:
        flush()
    if cfgCache == None:
        init()
        
    try:
        s = cfgCache[space]
    except:
        s = _loadSpace(space)
        
    if id(default) == id(__nodef):
        return s[var]
    else:
        return s.get(var, default)

def _loadSpace(space):
    """ Load a configuration file into the cache. 

    Args:
        space    - a namespace to load from cfgPath/space + ".py"
    """
    
    gdict = {}
    ldict = {}
    
    filename = os.path.join(cfgPath, "%s.py" % (space))
    try:
        execfile(filename, gdict, ldict)
    except SyntaxError, e:
        raise ICCError("syntax error at or before line %d (%s) of the configuration file %s" % (e.lineno, e.text, filename))
    except Exception, e:
        raise ICCError("failed to read the configuration file %s: %s" % (filename, e))
        
    cfgCache[space] = ldict
    return ldict

def _test():
    init('/tmp/cfg')
    print get('t1', 'x')
    print get('t1', 'x2')

if __name__ == '__main__':
    _test()
    
