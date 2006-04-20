""" 
Control enclosure devices.

Generally, all port names, states ("OPEN", "CLOSE, "ON", "OFF"), etc.
are assumed to be all upper case.
"""

import CPL
import client
import string

#LOGFD = file('/home/tron/logfile1','w')

def DEBUG(msg):
    '''Print messages to a file for debugging'''
    #LOGFD.write(msg+'\n')
    #LOGFD.flush()
    pass

class BadFanRequest(Exception):
    """
    Fan request asked for PRESSURIZATION with other fans or other
    fans are on.
    """
    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg

    def __str__(self):
        return self.msg

def hardware_names(parts, part_list):
    """
    For each name in parts, map to hardware name which is the
    part name's index in part_list + 1.  This should be the number to 
    pass to the enclosure controller to enable/disable the name.  

    Arguments:
        name - name to match in names
        names - list of possible names to match against
    """

    new_list = []
    for part in parts:
        new_list.append(str(part_list.index(part)+1))

    return new_list

class Enclosure:
    '''Enclosure control'''
    def __init__(self, devices):
        self.devices = devices
        self.order = range(len(devices))
        self.last_status = ''    # last enclosure status word
        DEBUG("devices: %s" % (str(devices)))
        DEBUG("devices keys: %s" % (str(devices.keys())))
        for key in devices.keys():
            DEBUG("key %s" % (key))
            DEBUG("%s" % (devices[key]))
            index = devices[key].index
            self.order[index] = key
        DEBUG("done, order: %s" % (str(self.order)))
    
    def enclosure_cmd(self, device, parts, state, cid, match=True):
        """ Send a command to the enclosure.
    
        Args:
           device - one of FAN, HEATER, LIGHT, and LOUVER
           parts - parts to turn on
           cmd	- the command string to send to the device. Should be one line.
           match - True, match partial names; False use name as is
    
        Returns:
           - the entire command response.
    
        Raises:
           - whatever call() raises.
        """
        part_list = self.devices[device].parts
    
        # map names to hardware names?
        if match:
            t_parts = hardware_names(parts, part_list)
        else:
            t_parts = [part for part in parts]

        t_parts.sort()
        msg = 'talk tcc_encl "%s.%s %s" ' % (device, state,  
            string.join(t_parts))
    
        return client.call('tcc', msg, cid=cid)
    
    def lights(self, names, state, cid):
        """
        Set the named lights to the state
    
        names - list of lights to act on.  Can be partial names.
        state - state is ON or OFF
        cid - command id
    
        Raises:
          - enclosure_cmd exceptions
        """
        DEBUG('Calling lights, names %s, state %s\n' % (str(names), state));
        return self.enclosure_cmd('LIGHT', names, state, cid)
    
    def louvers(self, names, state, cid):
        """
        Set the named louvers to the state
    
        names - list of lights to act on.  Can be partial names.
        state - state is OPEN, CLOSE, or AUTOMATIC
        cid - command id
    
        Raises:
          - enclosure_cmd exceptions
        """
        return self.enclosure_cmd('LOUVER', names, state, cid)
    
    def heaters(self, names, state, cid):
        """
        Set the named lights to the state
    
        names - list of lights to act on.  Can be partial names.
        state - state is ON or OFF
        cid - command id
    
        Raises:
          - enclosure_cmd exceptions
        """
        return self.enclosure_cmd('HEATER', names, state, cid, match=False)
    
    def enable(self, names, state, cid):
        """
        Set the named lights to the state
    
        names - list of lights to act on.  Can be partial names.
        state - state is ON or OFF
        cid - command id
    
        Raises:
          - enclosure_cmd exceptions
        """
        return self.enclosure_cmd('ENABLE', names, state, cid)
    
    def status(self, cid):
        """
        Read enclosure status and return as array of strings

        Returns:
            array of key/values
        """
        DEBUG("inside enclosure status")

        # read status
        msg = 'talk tcc_encl "STATUS"'
        DEBUG("get status from tcc_encl")
        stuff = client.call('tcc', msg, cid=cid)
        DEBUG("got status from tcc_encl")
        DEBUG("KVs: %s" % (str(stuff.KVs)))
        received = stuff.KVs['Received']
        DEBUG("pulled Received KV")
        # sometimes the received status gets confused
        # try a few times and see if you can get a repeatable value
        count = 3
        while received != self.last_status and count > 0:
            stuff = client.call('tcc', msg, cid=cid)
            received1 = stuff.KVs['Received']
            if received1 == received:   # seen it twice, must be good
                self.last_status = received
                break
            count = count - 1

        # if count == 0: raise an exception?

        # hopefully we now have a good status
        # received string is: "1 4  0 128     0 136", toss " with slice
        if received[0] == '"':
            received = received[1:-1]
        values = received.split()
        reply = {}
        DEBUG('len values %d, len order %d' % (len(values), len(self.order)))
        for i in range(len(values)):
            name = self.order[i]    # get the device
            value = int(values[i])  # set bits for parts that are open
            DEBUG('name %s, value %d' % (name, value))
            parts = self.devices[name].parts
            states = self.devices[name].states
            DEBUG('names %s' % (str(parts)))
            msg = {}
            index = 0
            # walk through value and if bit set (open), 
            # save part name chosen by index
            if name == 'SHUTTER':
                if value == 40:
                    msg[parts[0]] = states[1]
                    msg[parts[1]] = states[1]
                else:
                    msg[parts[0]] = states[0]
                    msg[parts[1]] = states[0]
            else:
                count = len(parts) - 1 # remember ALL is 1 extra
                while count > 0:
                    if value & 1:
                        msg[parts[index]] = states[1]
                    else:
                        msg[parts[index]] = states[0]
                    index = index + 1
                    value = value >> 1
                    count = count - 1
            DEBUG('msg is %s' % (str(msg)))
            reply[name] = msg

        DEBUG(str(reply))
        return reply
    
    def fans(self, names, state, cid):
        """
        Set the named fans to the state.  This tries to ensure
        that turning on pressurization fans will turn off enclosure
        fans.
    
        names - list of fans to act on.  Can be partial names.
        state - state is ON or OFF
        cid - command id
    
        Raises:
          - enclosure_cmd exceptions
          - BadFanRequest
        """
        return self.enclosure_cmd('FAN', names, state, cid)
