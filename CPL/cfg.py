""" A simple configuration manager. Loads python files in a given directory. That's it.
"""

__all__ = ['init', 'get', 'flush']

import os

def init(path):
    """ Initialize the cfg space.
    
    Args:
        path     - the directory inside which all the cfg files are kept.
    """
    global cfgPath
    
    cfgPath = path
    flush()

def flush():
    """ Clear any existing configuration cache.
    """

    global cfgCache
    
    cfgCache = {}

__nodef = 'no such variable HERE'
def get(space, var, default=__nodef):
    """ Fetch a configuration value.
    
    Args:
        space     - the namespace to search.
        var       - the name of the variable to get.
        default   ? if set, and var is not in space, return this.
    """
    
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
    
    cfgCache[space] = ldict
    return ldict

def _test():
    init('/tmp/cfg')
    print get('t1', 'x')
    print get('t1', 'x2')

if __name__ == '__main__':
    _test()
    
