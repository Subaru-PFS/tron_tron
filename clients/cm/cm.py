#!/usr/bin/env python

""" The "cm" command.

   REQSTAT
   REQPOS
   N offset
   S offset
   E offset
   W offset
   PT Eoffset,Noffset

   [ SLITPOS high/low ]

   Leftovers:
    - sexagesimal conversions
    - xs

"""

import inspect
import math
import pprint
import sys
import time
import traceback

import client
import Command
import Actor
import CPL

# Keyword conversion routines
def asFloat(v):
    if isinstance(v, str) and v.lower() == 'nan':
        return -9999
    else:
        return float(v)
        
def asFloat2(s):
    """ Parse a keyword as a pair of floats. """

    parts = s
    CPL.log("coords", "parts=%s" % (parts))
    floats = [asFloat(i) for i in parts]
    CPL.log("coords", "floats=%s" % (floats))
    if len(floats) != 2:
        raise ValueError("%r is not a valid float" % (s))
    return floats
        
def asCoord2(s):
    """ Parse a keyword as a TCC coord2: P,V,T,P2,V2,T2 """

    parts = s
    CPL.log("coords", "parts=%s" % (parts))
    coords = [asFloat(i) for i in parts]
    CPL.log("coords", "coord2=%s" % (coords))
    if len(coords) != 6:
        raise ValueError("%r is not a valid coord2" % (s))
    return coords
        
def asCoord(s):
    """ Parse a keywords as a TCC coord: P,V,T """

    parts = s
    CPL.log("coords", "parts=%s" % (parts))
    coords = [asFloat(i) for i in parts]
    CPL.log("coords", "coord=%s" % (coords))
    if len(coords) != 3:
        raise ValueError("%r is not a valid coord" % (s))
    return coords
        
def asPos3(s):
    """ Parse a keyword as a 3-axis TCC coordinate: Az,Alt,Pos. """

    parts = s
    CPL.log("coords", "parts=%s" % (parts))
    coords = [asFloat(i) for i in parts]
    CPL.log("coords", "pos3=%s" % (coords))
    if len(coords) != 3:
        raise ValueError("%r is not a valid pos3" % (s))
    return coords

def dmsStrFromDeg (decDeg, nFields=3, precision=1, omitExtraFields = False):
    """Converts a number to a sexagesimal string with 1-3 fields.

    Inputs:
        decDeg: value in decimal degrees or hours
        nFields: number of fields; <=1 for dddd.ddd, 2 for dddd:mm.mmm, >=3 for dddd:mm:ss.sss
        precision: number of digits after the decimal point in the last field
    """
    # first convert the number of seconds and round to the appropriate # of digits
    if precision > 0:
        minFloatWidth = precision + 3
    else:
        minFloatWidth = 2
    
    if decDeg < 0:
        signStr = "-"
        decDeg = abs(decDeg)
    else:
        signStr = ""
    
    if nFields <= 1  or (omitExtraFields and numSec == 0 and numMin == 0):
#           if nFields < 1 and decDeg == 0.0:
#               return ""
        return "%s%.*f" % (signStr, precision, decDeg)
    elif nFields == 2  or (omitExtraFields and numSec == 0):
        decDeg = float ("%.*f" % (precision, decDeg * 60.0)) / 60.0
        # now extract degrees, minutes and seconds fields
        (numDeg, frac) = divmod (abs(decDeg), 1.0)
        numMin = frac * 60.0
        return "%s%.0f:%0*.*f" % (signStr, numDeg, minFloatWidth, precision, numMin)
    else:
        # round decDeg to prevent roundup problems in the seconds field later
        decDeg = float ("%.*f" % (precision, decDeg * 3600.0)) / 3600.0
        if decDeg == -0.0:
            decDeg = 0.0  # works around a bug with -0.0: abs(-0.0) = -0.0
        # now extract degrees, minutes and seconds fields
        (numDeg, frac) = divmod (abs(decDeg), 1.0)
        (numMin, frac) = divmod (frac * 60.0, 1.0)
        numSec = frac * 60.0
        return "%s%.0f:%02.0f:%0*.*f" % (signStr, numDeg, numMin, minFloatWidth, precision, numSec)

class CM(Actor.Actor):
    """ Implement the command set required and sent by the CorMass instrument.  """
    
    def __init__(self, **argv):
        Actor.Actor.__init__(self, "cm", **argv)

        self.helpText = ("cm COMMAND",
                         "   COMMAND is one of:",
                         "     HELP         - return this",
                         "     REQSTAT      - return status",
                         "     REQPOS       - return position",
                         "     REQROT       - return rotator angle",
                         "     SLITPOS      - choose slit to put on boresight",
                         "     N offset",
                         "     E offset",
                         "     S offset",
                         "     W offset     - make arcsec offsets",
                         "     PT Eoffset Noffset  - make arcsec offsets",
                         "")
                         
        self.activeExposure = None
        self.activeCommand = None
        
        self.dispatch = { "REQSTAT" : self.doREQSTAT,
                          "REQPOS"  : self.doREQPOS,
                          "REQROT"  : self.doREQROT,
                          "SLITPOS" : self.doSLITPOS,
                          "N"       : self.doN,
                          "E"       : self.doE,
                          "S"       : self.doS,
                          "W"       : self.doW,
                          "PT"      : self.doPT,
                          "SETHIGH" : self.setHigh,
                          "HELP"    : self.doHELP
                          }

        self.highPos = (0.0, 3.0)
        self.slitPos = "low"
        
    def _parse(self, cmd):
        """
        """

        if self.debug >= 0:
            cmd.respond('cmDebug=%s' % (CPL.qstr(cmd.raw_cmd)))
            CPL.log("cm", "new command: %s" % (cmd.raw_cmd))

        # We parse the cm command set ad-hoc.
        #
        words = cmd.raw_cmd.split()

        # Ignore, but log, empty commands.
        #
        if len(words) == 0:
            CPL.log("cm", "empty command")
            cmd.finish('')
            return

        cmdWord = words[0].upper()
        f = self.dispatch.get(cmdWord)
        if not f:
            CPL.log("cm", "unknown command :%s:" % (words[0]))
            cmd.fail('RawTxt=%s' % (CPL.qstr("unknown command: %s" % (words[0]))))
            return

        try:
            self.activeCommand = cmd
            f(cmd, words[1:])
        except Exception, e:
            CPL.log("cm", "command failure: %s" % (e))
            cmd.fail('RawTxt=%s' % (CPL.qstr("command failure: %s" % (e))))
            self.activeCommand = None
            return

        self.activeCommand = None

    def doHELP(self, cmd, args):
        for s in self.helpText:
            cmd.respond('RawTxt=%s' % (CPL.qstr(s)))

    def _getTemps(self, cmd):
        """ Fetch some weather info.

        Returns:
          - (float) air temp
          - (float) secondary truss temp
          - (float) M1 front temp
          - (float) humidity
        """
        
        try:
            keys = client.getKeys("tcc", [('AirTemp', asFloat),
                                          ('SecTrussTemp', asFloat),
                                          ('PrimF_BFTemp', asFloat2),
                                          ('Humidity', asFloat)])
            cmd.respond('cmKeys=%s' % (CPL.qstr(keys)))

            return keys['AirTemp'], \
                   keys['SecTrussTemp'], \
                   keys['PrimF_BFTemp'][0], \
                   keys['Humidity']
        except:
            return -9999, -9999, -9999, -9999

    def doREQSTAT(self, cmd, args):
        """ Fetch all the status that CorMass wants.

        To wit:

        sscanf(com_buf,"UTC = %[^ ] LST = %[^ ] RA = %[^ ] DEC = %[^ ] "
                       "HA = %[^ ] AM = %f DEROTOFF = %f TDOMEAIR = %f "
                       "TSTRUT = %f TMIRROR = %f TMIRAIR = %f RELHUM = %f "
                       "SKYTEMP = %f FOCUS = %f FOCUSCMD = %f TIPX = %f "
                       "TIPXCMD = %f TIPY = %f TIPYCMD = %f GUIDING = %[^ ] "
                       "SLITPOS = %[^ ]",
        """

        airTemp, trussTemp, m1Temp, humidity = self._getTemps(cmd)
        
        client.call('tcc', 'show time')
        try:
            keys = client.getKeys("tcc", [('ObjPos', asCoord2),
                                          ('RotPos', asCoord),
                                          ('SecFocus', asFloat),
                                          ('UT1', asFloat),
                                          ('LST', asFloat),
                                          ('AxePos', asPos3)])
            cmd.respond('cmKeys=%s' % (CPL.qstr(keys)))
            
            ra = keys['ObjPos'][0]
            dec = keys['ObjPos'][3]
            raS = dmsStrFromDeg(ra / 15.0, precision=2)
            decS = dmsStrFromDeg(dec, precision=2)
            rotpos = keys['RotPos'][0]
            ut = keys['UT1'] + -3506716800.0
            utS = time.strftime("%H:%M:%S", time.gmtime(ut))
            lst = keys['LST']
            lstS = dmsStrFromDeg(lst / 15.0, precision=2)
            ha = lst - ra
            haS = dmsStrFromDeg(ha / 15.0, precision=2)
            alt = keys['AxePos'][1]
            am = 1.0 / math.sin(alt * math.pi/180)
            focus = keys['SecFocus']
        except Exception, e:
            cmd.warn("cmDebug=%s" % (CPL.qstr(e)))
            ra = -9999
            dec = -9999
            rotpos = -9999
            ut = -9999
            lst = -9999
            ha = -9999
            alt = -9999
            am = -9999
            focus = -9999
            
        s = "UTC = %s LST = %s RA = %s DEC = %s " + \
            "HA = %s AM = %0.2f DEROTOFF = %0.6f TDOMEAIR = %0.2f " + \
            "TSTRUT = %f TMIRROR = %f TMIRAIR = %f RELHUM = %f " + \
            "SKYTEMP = %f FOCUS = %f FOCUSCMD = %f TIPX = %f " + \
            "TIPXCMD = %f TIPY = %f TIPYCMD = %f GUIDING = %s " + \
            "SLITPOS = %s"
        resp = s % (utS, lstS, raS, decS, \
                    haS, am, rotpos, airTemp, \
                    trussTemp, m1Temp, -9999, humidity, \
                    -9999, -9999, focus, -9999, \
                    -9999, -9999, -9999, "true", \
                    self.slitPos)
        
        cmd.respond('cmDebug=%s' % (CPL.qstr(resp)))
        cmd.finish('RawTxt=%s' % (CPL.qstr(resp)))

    def doREQPOS(self, cmd, args):
        """ Fetch all the position info that CorMass wants.

        sscanf(com_buf,"UTC = %*[^ ] LST = %*[^ ] RA = %*[^ ] DEC = %*[^ ] "
        "HA = %*[^ ] AM = %*f DEROTOFF = %f",rot)

        """

        client.call('tcc', 'show time')
        try:
            keys = client.getKeys("tcc", [('ObjPos', asCoord2),
                                          ('RotPos', asCoord),
                                          ('UT1', asFloat),
                                          ('LST', asFloat),
                                          ('AxePos', asPos3)])
            cmd.respond('cmKeys=%s' % (CPL.qstr(keys)))
            
            ra = keys['ObjPos'][0]
            dec = keys['ObjPos'][3]
            raS = dmsStrFromDeg(ra / 15.0, precision=2)
            decS = dmsStrFromDeg(dec, precision=2)
            rotpos = keys['RotPos'][0]
            ut = keys['UT1'] + -3506716800.0
            utS = time.strftime("%H:%M:%S", time.gmtime(ut))
            lst = keys['LST']
            lstS = dmsStrFromDeg(lst / 15.0, precision=2)
            ha = lst - ra
            haS = dmsStrFromDeg(ha / 15.0, precision=2)
            alt = keys['AxePos'][1]
            am = 1.0 / math.sin(alt * math.pi/180)
        except Exception, e:
            cmd.warn("cmDebug=%s" % (CPL.qstr(e)))
            ra = -9999
            dec = -9999
            rotpos = -9999
            ut = -9999
            lst = -9999
            ha = -9999
            alt = -9999
            am = -9999
            
        s = "UTC = %s LST = %s RA = %s DEC = %s " + \
            "HA = %s AM = %0.2f DEROTOFF = %0.6f"
        resp = s % (utS, lstS, raS, decS, \
                    haS, am, rotpos)

        cmd.respond('cmDebug=%s' % (CPL.qstr(resp)))
        cmd.finish('RawTxt=%s' % (CPL.qstr(resp)))

    def doREQROT(self, cmd, args):
        """ Fetch the rotator info that CorMass wants.

        sscanf(com_buf,"DEROTOFF = %f",rot)
        """

        keysDir = client.getKeys("tcc",
                                 [('RotPos', float),
                                  ('RotType', None)])

        rotpos = keys['RotPos'][0]
        
        cmd.finish('RawTxt="DEROTOFF = %0.6f"' % (rotpos))
                   
    def parseOffsets(self, cmd, args):
        """ """
        if len(args) != 2:
            cmd.fail('RawTxt=%s' % \
                     (CPL.qstr("PT offset command takes two arguments (%s)" % (' '.join(args)))))
            return None, None
        try:
            f1 = float(args[0])
            f2 = float(args[1])
        except:
            cmd.fail('RawTxt=%s' % \
                     (CPL.qstr("offset arg is not a number (%s %s)" % (args[0], args[1]))))
            return None, None

        return f1, f2
        
    def parseOffset(self, cmd, args):
        """ """
        if len(args) != 1:
            cmd.respond('RawTxt="0"');
            cmd.fail('cmDebug=%s' % \
                     (CPL.qstr("offset commands take a single argument (%s)" % (' '.join(args)))))
            return None
        try:
            f = float(args[0])
        except:
            cmd.respond('RawTxt="0"');
            cmd.fail('cmDebug=%s' % \
                     (CPL.qstr("offset arg is not a single number (%s)" % (args[0]))))
            return None

        return f
        
    def doOffset(self, cmd, ew, ns, boreSight=False):
        total = math.sqrt(ew * ew + ns * ns)
        if boreSight:
            type = "boresight"
        else:
            type = "arc"
            
        if total <= 20:
            c = 'offset %s %0.6f,%0.6f' % (type, ew / 3600.0, ns / 3600.0)
        else:
            c = 'offset %s/computed %0.6f,%0.6f' % (type, ew / 3600., ns /3600.0)

        cmd.respond('cmDebug=%s' % (CPL.qstr(c)))
        cid = "%s.%s" % (cmd.fullname, self.name)
        res = client.call('tcc', c, cid=cid)

        cmd.finish('RawTxt="1"')

    def setOffset(self, cmd, args, offset):
        """ Define the offset from the boresight to one of the slit positions.

        Args:
            cmd
            args    - the unparsed command arguments.
            offset  - the variable to modify.
        """
        
        ew, ns = self.parseOffsets(cmd, args)
        if ew == None:
            cmd.fail('RawTxt="0"')
            return
        offset = ew, ns
        cmd.finish('RawTxt="1"')
        
    def setHigh(self, cmd, args):
        """ Define the offset from the boresight to the "upper" slit position. """

        ew, ns = self.parseOffsets(cmd, args)
        if ew == None:
            cmd.fail('RawTxt="0"')
            return
        self.highPos = ew, ns
        cmd.finish('RawTxt="1"')
        
    def doN(self, cmd, args):
        """ Offset North by the given number of arcseconds. """

        f = self.parseOffset(cmd, args)
        if f == None:
            cmd.fail('RawTxt=0')
            return
        
        self.doOffset(cmd, 0.0, f)
    
    def doE(self, cmd, args):
        """ Offset East by the given number of arcseconds. """

        f = self.parseOffset(cmd, args)
        if f == None:
            cmd.fail('RawTxt="0"')
            return

        self.doOffset(cmd, f, 0.0)
        
    def doS(self, cmd, args):
        """ Offset South by the given number of arcseconds. """

        f = self.parseOffset(cmd, args)
        if f == None:
            cmd.fail('RawTxt="0"')
            return

        self.doOffset(cmd, 0.0, -f)
    
    def doW(self, cmd, args):
        """ Offset West by the given number of arcseconds. """

        f = self.parseOffset(cmd, args)
        if f == None:
            cmd.fail('RawTxt="0"')
            return

        self.doOffset(cmd, -f, 0.0)
        
    def doPT(self, cmd, args):
        """ Offset East and North by the given number of arcseconds. """

        ew, ns = self.parseOffsets(cmd, args)
        if ew == None:
            cmd.fail('RawTxt="0"')
            return

        self.doOffset(cmd, ew, ns)
    
    def doSLITPOS(self, cmd, args):
        """ Choose one of the slits to move to the boresight. """

        if len(args) != 1:
            cmd.respond('RawTxt="0"');
            cmd.fail('cmDebug=%s' % (CPL.qstr("SLITPOS takes a single argument (%s)" % (' '.join(args)))))
            return None
        pos = args[0]
        if pos == 'high':
            self.doOffset(cmd, self.highPos[0], self.highPos[1], boreSight=True)
            self.slitPos = "high"
            cmd.finish('RawTxt="1"');
        elif pos == 'low':
            self.doOffset(cmd, -self.highPos[0], -self.highPos[1], boreSight=True)
            self.slitPos = "low"
            cmd.finish('RawTxt="1"');
        else:
            cmd.respond('RawTxt="0"');
            cmd.fail('cmDebug=%s' % (CPL.qstr("SLITPOS argument must be high or low (%s)" % (pos))))
            return None
        
# Start it all up.
#
def main(name, eHandler=None, debug=0, test=False):
    if eHandler == None:
        eHandler = CM(debug=9)
    eHandler.start()

    try:
        client.run(name=name, cmdQueue=eHandler.queue, background=False, debug=5, cmdTesting=test)
    except SystemExit, e:
        CPL.log('expose.main', 'got SystemExit')
        raise
    except:
        raise
    

def test():
    global mid
    mid = 1
    main('cm', test=True)

def tc(s):
    global mid
    
    client.cmd("APO CPL %d 0 %s" % (mid, s))
    mid += 1
    
if __name__ == "__main__":
    main('cm', debug=0)
