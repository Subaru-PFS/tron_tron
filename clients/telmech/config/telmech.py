'''
Configuration for telmech client
'''

class PortDef:
    'Conveniently define port definitions'
    def __init__(self, epos, port_id):
        self.epos = epos
        self.port_id = port_id
        self.eyelid_status = "?"


# Clockwise from NA2 (which is close to the home position):
ports = { 'BC1' : PortDef(782900, 1),
          'TR2' : PortDef(1101000, 2),
          'NA2' : PortDef(-1126600, 3),
          'TR3' : PortDef(-804350, 4),
          'BC2' : PortDef(-489300, -1),
          'TR4' : PortDef(-172600, 5),
          'NA1' : PortDef(146200, 6),
          'TR1' : PortDef(465580, 7),
          'HOME': PortDef(-1126600, 8)
          }

# eyelids
eyelids = [ 'BC1', 'TR2', 'NA2', 'TR3', 'BC2', 'TR4', 'NA1', 'TR1', 'ALL' ]

m3_alt_limit = 80.0     # do not move tertiary if alt < m3_alt_limit
m1_alt_limit =  0.0     # do not open covers if alt < m1_alt_limit

#
# Bit positions for the different devices
#
# NOT USED, but convenient for documentation
#
Enc_Enable = {'Power for enclosure rotation and axis motion':1}
Enc_Fan = {'Telescope Venting':1, 'Enclosure Venting':2,
           'Enclosure Pressurization':3}
Enc_Heater = {'Circuit 4':1, 'Circuit 8':2, 'Circuit 12':3, 'Circuit 16':4,
              'Circuit 20':5, 'Circuit 24':6}
Enc_Light = {'Obs-Level Front Halides':1, 'Obs-Level Rear Halides':2, 
             'Obs-Level Incandescents':3, 
             'Secondary Exchange Platform Incandescents':4, 
             'Catwalk Incandescents':5, 'Stairs Incandescents':6, 
             'Intermediate Incandescents':7, 'Intermediate Flourescents':8}
Enc_Louver = { 'Lower Left':1, 'Middle Left':2, 'Upper Left':3,
               'Lower Right':4, 'Middle Right': 5, 'Upper Right':6,
               'Stairs':7, 'RPit':8, 'LPit':9 }
Enc_Shutter = {'Left Shutter':1, 'Right Shutter':2}

#
# Enclosure devices.  The order is important.  The values are arranged in
# the bit order for the word.  For example, Heater 4 is the first bit.
# Also, 'OFF','ON' are 0 and 1.
#

class EnclosureDevice:
    def __init__(self, index, parts, states):
        self.index = index
        self.parts = parts
        self.states = states

enc_devices = {
    'ENABLE':EnclosureDevice(0,['TELESCOPE','ALL'],['OFF','ON']),
    'FANS':EnclosureDevice(1,['TELEXHAUST','INTEXHAUST','PRESS','ALL'],
                            ['OFF','ON']),
    'HEATERS':EnclosureDevice(2,['H4','H8','H12','H16','H20','H24','ALL'],
                               ['OFF','ON']),
    'LIGHTS':EnclosureDevice(3,['FHALIDES','RHALIDES','INCAND','PLATFORM',
                               'CATWALK','STAIRS','INT_INCAND',
                               'INT_FLOUR','ALL'],['OFF','ON']),
    'LOUVERS':EnclosureDevice(4,['LLOW','LMID','LUP','RLOW','RMID','RUP','STAIRS','RPIT',
                                'LPIT','ALL'],
                               ['CLOSE','OPEN']),
    'SHUTTERS':EnclosureDevice(5,['LEFT','RIGHT','ALL'],['CLOSE','OPEN'])
}

#
# Devices managed by telmech:
#
# Status can be gotten on all of them or individually.
#

devices = ['TERTROT', 'EYELID', 'COVERS', 'LIGHT', 'FAN', 'HEATER', 'LOUVER',
           'SHUTTER', 'ENABLE']

#
# Devices to return in devices query.  The order is needed to
# be fixed so TUI display is reproducible.  See telmech.py, _get_devices()
#
devices_to_get = ['LIGHT', 'FAN', 'SHUTTER', 'LOUVER', 'SHUTTER', 'ENABLE']
