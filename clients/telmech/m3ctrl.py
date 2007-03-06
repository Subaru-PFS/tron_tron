""" 
m3ctrl.py -- control the eyelids, the mirror covers, and tertiary rotation.

Generally, all port names, states ("OPEN", "CLOSE, "ON", "OFF"), etc.
are assumed to be all upper case.
"""

import CPL
import client
import call

#LOGFD = file('/home/tron/logfile2','w')

def DEBUG(msg):
    '''Print a message to a file'''
    #LOGFD.write(msg+'\n')
    #LOGFD.flush()
    pass

# The port rotations and the IDs of their eyelids.
# Counter-clockwise from the top; no port on the bottom (BC2).
#
def alt_status():
    """ 
    Ask the TCC the altitude status.

    Returns:
       - the entire command response.

    Raises:
       - whatever call() raises.
    """
    def as_float(value):
        '''
        Convert string to float
        '''
        if isinstance(value, str) and value.lower() == 'nan':
            return -9999
        return float(value)

    def as_pos3(str_value):
        """ Parse a keyword as a 3-axis TCC coordinate: Az,Alt,Pos. """

        parts = str_value
        coords = [as_float(i) for i in parts]
        if len(coords) != 3:
            raise ValueError("%r is not a valid pos3" % (str_value))
        return coords

    keys = client.getKeys("tcc", [('AxePos', as_pos3)])
    return keys['AxePos'][1]

class AltitudeToLow(Exception):
    '''
    Altitude too low to move M3 or open covers
    '''
    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg
    def __str__(self):
        return self.msg

class M3ctrl:
    '''
    Class to control the M3.  It is a class because there is a lot
    of state which needs to be remembered.
    '''
    def __init__(self, port_defs, eyelids, m1_alt_limit, m3_alt_limit):
        self.ports = port_defs
        self._eyelids = eyelids
        self.m1_alt_limit = m1_alt_limit
        self.m3_alt_limit = m3_alt_limit
        self.m3_select = "?"
        self.cover_status = "?"
        
    def tertrot(self, port, cid):
        """ Rotate the tertiary to one of the ports defined in .ports.
    
        Args:
           port	- the name of a port. Must be a key in the ports dictionary.
           "HOME" is a special name to home the tertiary.

        Raises:
            AltitudeToLow() exception
        """
        if alt_status() < self.m3_alt_limit:
            msg = 'M3 can not be rotated with telescope lower than %s degrees'\
                % (self.m3_alt_limit)
            raise AltitudeToLow(msg)

        DEBUG('looking for port %s' % (port));
        port_info = self.ports.get(port, None)
        if not port_info:
            DEBUG('did not find port_info');
            raise Exception("tertrot: no port named %s. Try %s" \
                % (port, ','.join(self.ports.keys())))
    
        DEBUG('found port_info');
        if port == "HOME":
            DEBUG('Home tertiary')
            cmd = 'E=0; XQ#HOME'
        else:
            pos = port_info.epos
            DEBUG('got EPos %d' % (pos))
            cmd = 'E=%d; XQ#MOVE' % (pos)

        reply = call.call(cmd)
        #reply = tcctalk('TCC_TERT', cmd, cid, timeout=90)
        # Assume it completed.  
        self.m3_select = port
        return reply
    
    def covers(self, state, cid):
        """ Open or close the mirror covers.
    
        Args:
           state	- 'open' or 'close'

        Raises:
            AltitudeToLow() exception
        """
    
        valid_states = {'OPEN' : "XQ#LOPCOV",
                        'CLOSE' : "XQ#LCLCOV"}
        
        cmd = valid_states.get(state)
        if not cmd:
            raise Exception("covers: invalid request: %s. Try %s" % \
                            (state, ' or '.join(valid_states.keys())))
   
        # close at any angle, open only if high enough
        if state == 'OPEN' and alt_status() < self.m1_alt_limit:
            msg = 'Covers can not be opened with telescope lower than %s \
degrees' % (self.m1_alt_limit)
            raise AltitudeToLow(msg)

        # First, close the eyelids, maybe remember them to reopen them
        # if covers are opened.
        self.eyelids(['ALL'], 'CLOSE', cid)
    
        call.call(cmd)
        #tcctalk('TCC_TERT', cmd, cid, timeout=30.0)
        # Assume covers did their thing
        self.cover_status = state
    
    def eyelids(self, names, state, cid):
        """ Open or close an eyelid, or close all eyelids.
    
        Args:
           names    - port names.
           state	- 'open' or 'close'
        """
        DEBUG('looking for states %s' % (state));

        name = names[0]
        if name not in self._eyelids:
            raise Exception("eyelid: invalid port name: %s. Try: %s" % \
                        (name, ', '.join(self._eyelids)))
    
        if name == 'ALL':
            # it must be a close command because incomplete open command caught
            # in telmech.py
            if state == 'CLOSE':
                call.call('XQ#LCLEYE')
                #tcctalk('TCC_TERT', 'XQ#LCLEYE', cid, timeout=30.0)
                for eyelid in self._eyelids:
                    if eyelid != 'ALL':
                        port = self.ports[eyelid]
                        port.eyelid_status = 'CLOSE'
            else:
                for eyelid in self._eyelids:
                    if eyelid != 'ALL':
                        self.one_eyelid(eyelid, state, cid)
        else:
            # open or close a single eyelid
            self.one_eyelid(name, state, cid)
        return
    
    def one_eyelid (self, name, state, cid):
        """ Open or close a single eyelid.
    
        Args:
           name     - port names.
           state	- 'open' or 'close'
        """
        valid_states = {'OPEN' : "XQ#LOPEYE",
                        'CLOSE' : "XQ#LCLEYE" }
        cmd = valid_states.get(state)
        port = self.ports[name]
        full_cmd = "A=%s; %s" % (port.port_id, cmd)
    
        DEBUG("Command eyelid %s" % (name))
        DEBUG("Command eyelid command %s" % (full_cmd))
        DEBUG("eyelid status is %s" % (str(port.eyelid_status)))

        # assume it happened - To Be Done: read status and set this
        port.eyelid_status = state
            
        DEBUG('full cmd %s' % (full_cmd));
        return call.call(full_cmd)
        #return tcctalk('TCC_TERT', full_cmd, cid, timeout=30.0)
    
    def status(self):
        '''
        Return the M3 status as a series of keywords.
        '''
        reply = {}
        reply['COVERS'] = self.cover_status
        reply['TERTROT'] = self.m3_select
        save = {}
        for key in self._eyelids:
            if key != 'ALL':        # everything but ALL
                port = self.ports[key]
                save[key] = port.eyelid_status
        reply['EYELIDS'] = save

        return reply
