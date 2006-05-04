#!/usr/bin/env python
"""
Control 3.5m mechanical devices.

To start telmech with TUI, enter this from the log command line:

    hub startNubs telmech

Once started, you can command telmech devices by entering commands
with the log command line.  Type telmech plus one of the following
commands.  Each command configures a device state.  The commands,
devices, and state can take as few as a single unique character in
the name.  If the characters do not uniquely select the part, then 
you will get an error.

For example, to close all eyelids:

  telmech e a c       - eyelid all close
  telmech f i t n     - turn on intexhaust, telexhaus fans and
                        turn off pressurization

Commands:
    ? - print commands

    tertrot - set tertiary to this port

        usage: tertrot portname
            portname is one of the ports or home to home the tertiary rotation

    eyelid - set the eyelid state for a single eyelid or ALL eyelids
        usage: eyelid port state
            state is either open or close
            eyelid is one of the eyelid names or ALL

    cover - open or close the covers
        usage: cover state
            state is either open or close
  
    light - turn on/off lights
        usage: light light1 [light2 [...]] state
        light1, light2, ... are the light names or ALL
        state is on or off
  
    fan  - turn on/off fans
        usage: fan fan1 [fan2 [...]] state
        fan1, fan2, ... are the fan names or ALL
        state is on or off

    louver - open/close louvers
        usage: louver louver1 [louver2 [...]] state
        louver1, louver2, ... are the louver names or ALL
        state is on or off
  
    status [device]
        device is one of the devices above, i.e. tertrot, eyelid, cover, light,
        fan, and louver

    devices - return the devices that have parts and the part names.
        The enclosure devices are the only devices that meet this condition.
        usage: devices

For example:

tui> telmech ?
    should printout telmech commands

tui> telmech eyelid

    should print out the usage and list the ports which can be set

tui> telmech light incan on

    should turn on incandescents on the observing level

To Be Done: 
    The m3 hardware status is not used in this version.  So, moving
    the tertiary, opening/closing eyelids, etc., do not have feedback if the
    move was successful or not.  A lot more work is needed to make this
    more robust.

    The commands are going through the tcc.  In future versions, the tcc
    should be taken out of the middle and the commands should go directly
    to the controllers.

    Identify missing commands.  One that comes to mind is to be able
    to have status as one of the options to a device command.  For example,

        telmech fan status

    But, for the meantime, just use

        telmech status fan
"""

import sys
import string

import client
import CPL
import Actor

import m3ctrl
import enclosure
from match_utils import *

from traceback import print_exc
LOGFD = file('/home/tron/logfile', 'w')

def DEBUG(msg):
    '''Debug print message to a file'''
    LOGFD.write(msg+'\n')
    LOGFD.flush()
    pass

def DEBUG_EXC():
    '''Debug print stack trace to a file'''
    #print_exc(file=LOGFD)
    #LOGFD.flush()
    pass

class Telmech(Actor.Actor):
    """ 
    Control the telescope mechanical devices.
    """
    def __init__(self, **argv):
        # devices managed by telmech, should agree with local_commands
        self.devices = CPL.cfg.get('telmech', 'devices')
        self.devices_to_get = CPL.cfg.get('telmech', 'devices_to_get')

        Actor.Actor.__init__(self, 'telmech', **argv)
        # make sure the devices here agree with the devices in config/telmech.py
        self.commands.update({'tertrot': self._set_tert_cmd,
                              'eyelid': self._set_eyelids_cmd,
                              'cover': self._set_covers_cmd,
                              'light': self._set_lights_cmd,
                              'fan': self._set_fans_cmd,
                              'heater': self._set_heaters_cmd,
                              'louver': self._set_louvers_cmd,
                              'status': self._get_status,
                              'devices': self._get_devices})

        self.ports = CPL.cfg.get('telmech', 'ports')
        self.eyelids = CPL.cfg.get('telmech', 'eyelids')
        self.m1_alt_limit = CPL.cfg.get('telmech', 'm1_alt_limit')
        self.m3_alt_limit = CPL.cfg.get('telmech', 'm3_alt_limit')
        self.m3_ctrl = m3ctrl.M3ctrl(self.ports, self.eyelids, 
                                     self.m1_alt_limit, self.m3_alt_limit)
        self.enc_devices = CPL.cfg.get('telmech', 'enc_devices')
        self.enclosure = enclosure.Enclosure(self.enc_devices)

    def _parse(self, cmd):
        """ Default parsing behavior. Simply calls a Command's handler.

        Args:
            cmd  - a Command instance. The first word of the command text is 
                   used as a key in .commands.

        If the command word is found, the handler is called. If not, the 
        command is failed.
        """

        # Actively reject empty commands. Maybe this should just ignore them.
        #
        if len(cmd.argDict) == 0:
            cmd.warn('%sTxt="empty command"' % (self.name))
            cmd.finish()
            return

        # Find the handler and call it.
        #
        cmdWords = cmd.argDict.keys()
        cmdWord = cmdWords[0]
        # match cmdWord 
        try:
            cmdWord = match_name(cmdWord, self.commands.keys())
        except BadNameMatch, exc_obj:
            pass
        handler = self.commands.get(cmdWord, None)
        if not handler:
            cmd.fail('%sTxt=%s' % \
                  (self.name, CPL.qstr('unknown command %s, try one of %s') % \
                                   (cmdWord, ', '.join(self.commands.keys()))))
            return
        handler(cmd)

    def _set_tert_cmd(self, cmd):
        """ Handle tertrot command.

        CmdArgs:
           str - port name
        """

        parts = cmd.raw_cmd.split()
        msg = 'parts length %d' % (len(parts))
        if len(parts) != 2:
            msg = '''usage: tertrot port. \
Ports are: %s''' % (string.join(self.ports.keys()))
            cmd.fail('errtxt="'+msg+'"')
            return

        try:
            cid = self.cidForCmd(cmd)
            part = parts[1].upper()
            part = match_name(part, self.ports.keys())
            self.m3_ctrl.tertrot(part, cid)
        except:
            msg = 'errtxt=' + '"'+str(sys.exc_info()[1])+'"'
            cmd.fail(msg)
            return

        cmd.finish()

    def _set_eyelids_cmd(self, cmd):
        """ Handle eyelids command.

        Code written to handle multiple eyelids, but m3ctrl really uses
        the first eyelid.  Don't tell users about multiple eyelids until
        fully implemented.

        CmdArgs:
           str - open or close.
        """

        parts = cmd.raw_cmd.split()
        if len(parts) < 3:
            msg = '''usage: eyelid port-name open/close. \
Ports are: %s''' % (string.join(self.eyelids))
            cmd.fail('errtxt="'+msg+'"')
            return

        DEBUG("Parts are: %s" % (str(parts)))
        state = parts[-1].upper()
        DEBUG("State is: %s" % (state))
        try:
            state = match_name(state, ['OPEN', 'CLOSE'])
        except:
            msg = '''usage: eyelid port-name open|close. \
Ports are: %s''' % (string.join(self.eyelids))
            cmd.fail('errtxt="'+msg+'"')
            return

        try:
            cid = self.cidForCmd(cmd)
            DEBUG("parts are: %s" % str(parts[1:-1]))
            part_list = map(lambda x: x.upper(), parts[1:-1])
            part_list = match_names(part_list, self.eyelids)
            self.m3_ctrl.eyelids(part_list, state, cid)
        except:
            DEBUG_EXC()
            msg = 'errtxt=' + '"'+str(sys.exc_info()[1])+'"'
            cmd.fail(msg)
            return

        cmd.finish()

    def _set_covers_cmd(self, cmd):
        """ Handle cover command.

        CmdArgs:
           str - open or close.
        """

        parts = cmd.raw_cmd.split()
        if len(parts) != 2:
            cmd.fail('errtxt="usage: cover open|close."')
            return

        try:
            cid = self.cidForCmd(cmd)
            part = parts[1].upper()
            part = match_name(part, ['OPEN', 'CLOSE'])
            self.m3_ctrl.covers(part, cid)
        except:
            DEBUG_EXC()
            msg = 'errtxt=' + '"'+str(sys.exc_info()[1])+'"'
            cmd.fail(msg)
            return;

        cmd.finish()

    def _set_lights_cmd(self, cmd):
        """ 
        Handle light command

        CmdArgs:
           str - name(s) and on/off.
        """
        parts = cmd.raw_cmd.split()
        if len(parts) < 3:
            msg = '''usage: light [light1 [light2 ...]] [on|off]. \
Lights are: %s''' % (string.join(self.enc_devices['LIGHT'].parts))
            cmd.fail('errtxt="'+msg+'"')
            return

        state = parts[-1].upper()
        try:
            state = match_name(state, ['ON', 'OFF'])
        except:
            msg = '''light state %s not uniquely 'on' or 'off'.''' % (state)
            cmd.fail('errtxt="'+msg+'"')

        try:
            cid = self.cidForCmd(cmd)
            part_list = map(lambda x: x.upper(), parts[1:-1])
            part_list = match_names(part_list, self.enc_devices['LIGHT'].parts)
            if 'ALL' in part_list:
                part_list = all_names(self.enc_devices['LIGHT'].parts)
            self.enclosure.lights(part_list, state, cid)
        except:
            msg = 'errtxt=' + '"'+str(sys.exc_info()[1])+'"'
            cmd.fail(msg)
            return;

        cmd.finish()

    def _set_fans_cmd(self, cmd):
        """ 
        Handle fan command.

        CmdArgs:
           str - name(s) and on/off.
        """

        parts = cmd.raw_cmd.split()
        if len(parts) < 3:
            msg = '''usage: fan [fan1 [fan2 ...]] [on|off]. \
Fans are: %s''' % (string.join(self.enc_devices['FAN'].parts))
            cmd.fail('errtxt="'+msg+'"')
            return

        state = parts[-1].upper()
        try:
            state = match_name(state, ['ON', 'OFF'])
        except:
            msg = '''fan state %s not uniquely 'on' or 'off'.''' % (state)
            cmd.fail('errtxt="'+msg+'"')

        try:
            cid = self.cidForCmd(cmd)
            part_list = map(lambda x: x.upper(), parts[1:-1])
            part_list = match_names(part_list, self.enc_devices['FAN'].parts)
            if 'ALL' in part_list:
                part_list = all_names(self.enc_devices['FAN'].parts)
            self.enclosure.fans(part_list, state, cid)
        except:
            DEBUG_EXC()
            msg = 'errtxt=' + '"'+str(sys.exc_info()[1])+'"'
            cmd.fail(msg)
            return;

        cmd.finish()

    def _set_heaters_cmd(self, cmd):
        """ 
        Handle heater command.

        CmdArgs:
           str - name(s) and on/off.
        """

        parts = cmd.raw_cmd.split()
        if len(parts) < 3:
            msg = '''usage: heater [heater1 [heater2 ...]] [on|off]. \
Heaters are: %s''' % (string.join(self.enc_devices['HEATER'].parts))
            cmd.fail('errtxt="'+msg+'"')
            return

        state = parts[-1].upper()
        try:
            state = match_name(state, ['ON', 'OFF'])
        except:
            msg = '''heater state %s not uniquely 'on' or 'off'.''' % (state)
            cmd.fail('errtxt="'+msg+'"')

        try:
            cid = self.cidForCmd(cmd)
            part_list = parts[1:-1]     # '1', '2', ... - no name expand
            if 'ALL' in part_list:
                part_list = all_names(self.enc_devices['HEATER'].parts)
            self.enclosure.heaters(part_list, state, cid)
        except:
            msg = 'errtxt=' + '"'+str(sys.exc_info()[1])+'"'
            cmd.fail(msg)
            return;

        cmd.finish()

    def _set_louvers_cmd(self, cmd):
        """ 
        Handle louver command.

        CmdArgs:
           str - name(s) and on/off.
        """

        parts = cmd.raw_cmd.split()
        if len(parts) < 3:
            msg = '''usage: louver [louver1 [louver2 ...]] [on|off]. \
Louvers are: %s''' % (string.join(self.enc_devices['LOUVER'].parts))
            cmd.fail('errtxt="'+msg+'"')
            return

        state = parts[-1].upper()
        try:
            state = match_name(state, ['ON', 'OFF'])
        except:
            msg = '''louver state %s not uniquely 'on' or 'off'.''' % (state)
            cmd.fail('errtxt="'+msg+'"')

        try:
            cid = self.cidForCmd(cmd)
            part_list = map(lambda x: x.upper(), parts[1:-1])
            part_list = match_names(part_list, self.enc_devices['LOUVER'].parts)
            if 'ALL' in part_list:
                part_list = all_names(self.enc_devices['LOUVER'].parts)
            self.enclosure.louvers(part_list, state, cid)
        except:
            msg = 'errtxt=' + '"'+str(sys.exc_info()[1])+'"'
            cmd.fail(msg)
            return;

        cmd.finish()

    def _get_status(self, cmd):
        """ 
        Handle status command
        """

        parts = cmd.raw_cmd.split()
        if len(parts) not in [1, 2]:
            cmd.fail('errtxt="usage: status [device], optional devices are: %s"\
' % (string.join(self.devices)))
            return

        device = ''
        try:
            if len(parts) == 2:
                if parts[1].upper() in self.devices:
                    device = parts[1].upper()
                else:
                    cmd.fail('errtxt="device %s not recognized.  \
Devices are: %s"' % (parts[1], string.join(self.devices)))
                    return
        except:
            DEBUG_EXC()

        try:
            cid = self.cidForCmd(cmd)
            reply = self.enclosure.status(cid)
            reply.update(self.m3_ctrl.status())

            if device != '':        # select just this one
                new_reply = {}
                new_reply[device] = reply[device]
                reply = new_reply
        except:
            DEBUG_EXC()
            msg = 'errtxt=' + '"'+str(sys.exc_info()[1])+'"'
            cmd.fail(msg)
            return;

        for device in reply:
            msg = 'device=%s' % (device.lower())
            # not a dictionary, just a value
            if device not in ['COVERS', 'TERTROT']:     
                parts = reply[device]
                fmt = ';%s=%s'
                for part in parts:
                    msg = msg + fmt % (part.lower(), parts[part].lower())
                cmd.respond(msg)
            else:
                msg = msg + ';value=%s' % (reply[device].lower())
                cmd.respond(msg)

        cmd.finish()

    def _get_devices(self, cmd):
        """ 
        Return devices list
        """
        messages = []

        DEBUG('devices to get %s' % (str(self.devices_to_get)))
        for device in self.devices_to_get:
            try:
                # all but ALL
                parts = self.enc_devices[device].parts[:-1]
                parts = map(lambda x: x.lower(), parts)
                msg = '%s=%s' % (device.lower(), string.join(parts,','))
                DEBUG('msg %s' % (msg))
                messages.append(msg)
            except:
                pass
        
        DEBUG('messages: %s' % (str(messages)))
        DEBUG('full msg %s' % (string.join(messages,';')))
        cmd.respond(string.join(messages,';'))
        cmd.finish()

#
# Start it all up.
#

#
# Start it all up.
#
def main(name, eHandler=None, debug=0, test=False):
    actor = Telmech(debug=debug)
    actor.start()

    client.run(name=name, cmdQueue=actor.queue,
               background=False, debug=debug, cmdTesting=test)

if __name__ == "__main__":
    main('telmech', debug=1)
