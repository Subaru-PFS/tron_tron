""" m3.py -- control the eyelids, the mirror covers, and tertiary rotation."""

import CPL
from client import *

# The port rotations and the IDs of their eyelids.
# Counter-clockwise from the top; no port on the bottom (BC2).
#
ports = { 'BC1' : { "EPos" : 782630, "eyelidID" : 1 },
          'TR2' : { "EPos" : 1100880, "eyelidID" : 2 },
          'NA2' : { "EPos" : -11270000, "eyelidID" : 3 },
          'TR3' : { "EPos" : -808750, "eyelidID" : 4 },
          'BC2' : { "EPos" : -490500, "eyelidID" : -1 },
          'TR4' : { "EPos" : -172000, "eyelidID" : 5 },
          'NA1' : { "EPos" : 146000, "eyelidID" : 6 },
          'TR1' : { "EPos" : 464380, "eyelidID" : 7 }
          }

def tcctalk(device, cmd, timeout=60.0):
    """ Send a command to a device connected to the TCC, using the TCC's TALK command.

    Args:
       device	- the name of the device to command. e.g. TCC_TERT
       cmd	- the command string to send to the device. Should be one line.
       timeout	- control the TALK command's timout.

    Returns:
       - the entire command response.

    Raises:
       - whatever call() raises.
    """

    return call('tcc', 'TALK %s %s /TIMEOUT=%0.1f' % (device, CPL.qstr(cmd), timeout))
    
def tertrot(port):
    """ Rotate the tertiary to one of the ports defined in .ports.

    Args:
       port	- the name of a port. Must be a key in the ports dictionary
    """

    portInfo = ports.get(port, None)
    if not pos:
        raise Exception("tertrot: no port named %s. Try %s" % (port, ','.join(ports.keys())))

    pos = portInfo['EPos']
    return tcctalk('TCC_TERT', 'E=%d; XQ#MOVE' % (pos), timeout=90.0)

def covers(state):
    """ Open or close the mirror covers.

    Args:
       state	- 'open' or 'close'
    """

    validStates = {'open' : "XQ#LOPCOV",
                   'close' : "XQ#LCLCOV"
                   }
    
    cmd = validStates.get(state)
    if not cmd:
        raise Exception("covers: invalid request: %s. Try %s" % \
                        (state, ' or '.join(validStates.keys())))

    return tcctalk('TCC_TERT', cmd, timeout=30.0)

def eyelids(state, name=None):
    """ Open or close an eyelid, or close all eyelids.

    Args:
       state	- 'open' or 'close'
       name     - one port name.
    """

    validStates = {'open' : "XQ#LOPEYE",
                   'close' : "XQ#LCLEYE"
                   }
    
    cmd = validStates.get(state)
    if not cmd:
        raise Exception("eyelids: invalid request: %s. Try %s" % \
                        (state, ' or '.join(validStates.keys())))

    if name == None and state == 'open':
        raise Exception("eyelids: which eyelid do you want to open?" % \
                        (state, ' or '.join(validStates.keys())))

    port = ports.get(name, None)
    if port == None
        raise Exception("eyelids: invalid port name: %s. Try: %s" % \
                        (name, ', '.join(ports.keys())))

    portID = port['eyelidID']
    if name == None:
        fullCmd = cmd
    else:
        fullCmd = "A=%s; %s" % (portID, cmd)
        
    return tcctalk('TCC_TERT', fullCmd, timeout=30.0)

    

    
    
