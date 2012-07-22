__all__ = ['setID',
           'setLogfile',
           'enableLoggingFor', 'disableLoggingFor',
           'isoTS',
           'log', 'error']

import sys

from time import time, gmtime, strftime
from math import modf

systems = {}
id = ""

DISABLED = '0'
ENABLED = '.'
ERROR = 'E'
FATAL = 'F'
UNDEFINED = '?'

def setID(newID):
    global id
    
    id = newID

def setLogdir(dirname):
    global logdir
    
def setLogfile(filename, truncate=False):
    global logfile
    
    if hasattr(globals(), 'logfile'):
        logfile.close()
        logfile = None
        
    try:
        if truncate:
            logfile = file(filename, 'w+', 1)
        else:
            logfile = file(filename, 'a+', 1)
            
    except:
        logfile = sys.stderr
        log('log.setLogfile', 'could not open logfile %r for appending' % (filename,))
        
def enableLoggingFor(system):
    systems[system] = ENABLED

def disableLoggingFor(system):
    systems[system] = DISABLED
    
def setLoggingFor(system, level):
    if level:
        systems[system] = ENABLED
    else:
        systems[system] = DISABLED
    
def isoTS(t=None, format="%Y-%m-%d %H:%M:%S", zone="Z"):
    """ Return a proper ISO timestamp for t, or now if t==None. """

    if t == None:
        t = time()

    if zone == None:
        zone = ''
        
    return strftime(format, gmtime(t)) \
           + ".%03d%s" % (1000 * modf(t)[0], zone)
    
def log(system, detail, state=None):
    now = isoTS()
    
    if not hasattr(globals(), 'logfile'):
        logfile = sys.stderr
        
    # If the logging state has not explicitely been enabled or disabled,
    # print the notice, but mark the system name with a '?'
    #
    if state == None:
        state = systems.get(system, UNDEFINED)

    if state == UNDEFINED:
        state = systems.get('default', state)
        
    if state != DISABLED:
        logfile.write("%s %s %s %s %s\n" % (now, id, state, system, detail))
        logfile.flush()
        
def error(*args):
    apply(log, args, {'state':ERROR})
    
