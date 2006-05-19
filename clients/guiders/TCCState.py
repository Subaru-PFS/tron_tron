""" TCCState.py -- listen to the TCC, and alert other objects when it "moves".
"""

import time

import CPL
import Parsing
import client

class DevNull(object):
    """ Accept any method call, and ignore it. """

    def devnull(self, *argl, **argv):
        return True

    def __getattr__(self, name):
        CPL.log('TCCState', 'devnulling %s' % (name))
        return self.devnull

    
class TCCState(object):
    def __init__(self, type):
        """
        Args:
            type    - 'gimage' or 'inst'
        """
        
        self.listeners = []
        self.interestedParty = DevNull()
            
        # Are we an instrument (slitviewers usually are), or an offset guider?
        #
        self.frameName = type
        if type == 'gimage':
            self.imCtrName = 'GImCtr'
            self.imScaleName = 'GImScale'
        elif type == 'inst':
            self.imCtrName = 'IImCtr'
            self.imScaleName = 'IImScale'
        else:
            raise RuntimeError("unknown guider type: %s" % (type))

        self.instName = None
        self.listenToThem()

        self.UTCoffset = 0.0
        i = 0
        while i < 10:
            CPL.log('TCCState', 'startup(%d)=%s' % (i, self))
            i += 1
            time.sleep(0.25)

    def __str__(self):
        return("TCCState(listeners=%s)" % (self.listeners))
    
    def __del__(self):
        """ Need to actively stop any listeners. """
        
        for i in range(len(self.listeners)):
            CPL.log("TCCState.cleanup", "deleting listener %s" % (self.listeners[0]))
            self.listeners[0].stop()
            del self.listeners[0]

    def connectToMe(self, o):
        """ Register some object which cares about telscope things. """

        self.interestedParty = o
        CPL.log('TCCState', 'listening to %s' % (o))
        
    def disconnectFromMe(self, o):
        """ Unregister some object which used to care about telscope things. """

        self.interestedParty = DevNull()
            
    def listenToThem(self):
        """ Create all the TCC keyword listeners. """

        CPL.log("TCCState", "starting listeners...")
       
        self.listeners.append(client.listenFor('tcc', ['MoveItems', 'Moved', 'SlewBeg', 'Inst'],
                                               self.listenToMoveItems))
        self.listeners.append(client.listenFor('tcc', ['TCCStatus'],
                                               self.listenToTCCStatus))
        self.listeners.append(client.listenFor('tcc', ['Boresight'],
                                               self.listenToTCCBoresight))
        self.listeners.append(client.listenFor('tcc', ['UTC_TAI'],
                                               self.listenToTCCUTC_TAI))
        self.listeners.append(client.listenFor('tcc', [self.imCtrName],
                                               self.listenToTCCImCtr))
        self.listeners.append(client.listenFor('tcc', [self.imScaleName],
                                               self.listenToTCCImScale))

        self.listeners.append(client.listenFor('tcc', ['SlewEnd'],
                                               self.listenToTCCSlewEnd))

        # Force updates of the above keywords:
        client.call("tcc", "show inst/full") # ImCtr, ImScale, Inst
        client.call("tcc", "show object") # Boresight
        client.call("tcc", "show time")

        CPL.log("TCCState", "done with listeners...")

    def listenToMoveItems(self, reply):
        """ Figure out if the telescope has been moved by examining the TCC's MoveItems key.

        The MoveItems keys always comes with one of:
          - Moved, indicating an immediate offset
              We guestimate the end time, and let the main loop wait on it.
          - SlewBeg, indicating the start of a real slew or a computed offset.
              We
          - SlewEnd, indicating the end of a real slew or a computed offset
        """

        
        if reply.KVs.has_key('Inst'):
            inst = reply.KVs.get('Inst', 'None')
            inst = Parsing.dequote(inst)
            if inst != self.instName:
                oinst = self.instName
                self.instName = inst
                if oinst != None:
                    self.interestedParty.telescopeHasMoved(True, newField=True, how="Instrument changed")
                    return

        # Has an uncomputed offset just been issued?
        if reply.KVs.has_key('Moved'):
            self.interestedParty.telescopeHasMoved(False)
            return
        
        mi = reply.KVs.get('MoveItems', 'XXXXXXXXX')
        mi = Parsing.dequote(mi)

        CPL.log('listenToMoveItems', 'mi=%s' % (mi))
        
        newField = False
        if mi[1] == 'Y':
            what = 'Telescope has been slewed'
            newField = True
        elif mi[3] == 'Y':
            what = 'Object offset was changed'
        elif mi[4] == 'Y':
            what = 'Arc offset was changed'
        elif mi[5] == 'Y':
            what = 'Boresight position was changed'
        elif mi[6] == 'Y':
            what = 'Rotation was changed'
        elif mi[8] == 'Y':
            what = 'Calibration offset was changed'
        else:
            # Ignoring:
            #    mi[0] - Object name
            #    mi[2] - Object magnitude
            #    mi[7] - Guide offset
            # CPL.log('listenToMoveItems', 'ignoring ip=%s, kvs=%s' % (self.interestedParty, reply.KVs))
            return
        
        CPL.log('listenToMoveItems', 'ip=%s, kvs=%s' % (self.interestedParty, reply.KVs))

        # Has a slew/computed offset just been issued? 
        if reply.KVs.has_key('SlewBeg'):
            self.interestedParty.telescopeHasMoved(True, newField=newField, how=what)
        
    def listenToTCCStatus(self, reply):
        """ Figure out if the telescope has been halted by examining the TCC's TCCStatus key.
        """

        stat = reply.KVs['TCCStatus']
        axisStat = stat[0]

        if 'H' in axisStat:
            self.interestedParty.telescopeHasHalted()
    
    def listenToTCCSlewEnd(self, reply):
        """ Wait for a computed offset to finish.
        """

        self.interestedParty.telescopeSlewIsDone()
        
    def listenToTCCBoresight(self, reply):
        """ Figure out if the telescope has been moved by examining the TCC's TCCStatus key.
        """
        
        k = reply.KVs['Boresight']
        pvt = list(map(float, k))
        self.boresightOffset = pvt
        CPL.log('GuideLoop', "set boresight offset to (%s)" % (self.boresightOffset))
    
    def listenToTCCImCtr(self, reply):
        """ Set the guider/instrument center pixel.
        """

        k = reply.KVs[self.imCtrName]
        self.boresight = map(float, k)
        CPL.log('GuideLoop', "set boresight pos to (%0.2f, %0.2f)" % \
                (self.boresight[0], self.boresight[1]))
        
    def listenToTCCImScale(self, reply):
        """ Set the guider/instrument scales.
        """

        k = reply.KVs[self.imScaleName]
        self.imScale = map(float, k)
        CPL.log('GuideLoop', "set imscale to (%0.2f, %0.2f)" % \
                (self.imScale[0], self.imScale[1]))
        
    def listenToTCCUTC_TAI(self, reply):
        """ Set the UTC-TAI offset
        """

        k = reply.KVs['UTC_TAI']

        self.UTCoffset = float(k)
        self.tccDtime = -3506716800.0 + self.UTCoffset

        CPL.log('GuideLoop', "set UTC offset to (%0.2f)" % (self.UTCoffset))
        
    def TAI2UTC(self, tai):
        """ Convert from the TCC's TAI to Unix UTC. """
        
        return tai + self.tccDtime

    def UTC2TAI(self, utc):
        """ Convert from Unix UTC to the TCC's TAI. """

        return utc - self.tccDtime
    
    def PVT2pos(self, pvt, t=None):
        """ Evaluate a PVT to the given time (or to now).

        Args:
             pvt     - a TCC coord2 (p,v,t,p2,v2,t2)
             t       - a UTC time. If None, use "now".

        Returns:
             (x, y)
        """

        CPL.log('PVT2pos', CPL.qstr("PVT2pos(utc=%s, pvt=%s)" % (t, pvt)))

        if not t:
            t = time.time()
        t = self.UTC2TAI(t)

        CPL.log('PVT2pos', CPL.qstr("PVT2pos(tai=%s, pvt=%s)" % (t, pvt)))

        td = t - pvt[2]
        x = pvt[0] + pvt[1] * td
        
        td = t - pvt[5]
        y = pvt[3] + pvt[4] * td

        CPL.log('PVT2pos', CPL.qstr("td=%0.4f; x=%0.4f; y=%0.4f)" % (td, x, y)))

        return x, y

    def getBoresight(self, t=None):
        """ Figure out the boresight position for a given time.

        The effective boresight is the sum of the instrument/guider center and the
        boresight offset. 

        Args:
             t       ? time, in Unix seconds, to reckon the boresight at.

        Returns:
            - the boresight position at t, as an x,y pair of pixel
        """

        if t == None:
            t = time.time()

        # Evaluate the boresight offset for t. In degrees.
        bsPos = self.PVT2pos(self.boresightOffset, t)

        # Add the offset to the ImCtr boresight pixel.
        xPos = self.boresight[0] + self.imScale[0] * bsPos[0]
        yPos = self.boresight[1] + self.imScale[1] * bsPos[1]

        # self.cmd.warn('debug="boresight is at (%0.2f, %0.2f)"' % (xPos, yPos))
        return xPos, yPos

    def _extractCnvPos(self, res):
        """ Extract and convert the converted position from a tcc convert.

        Returns:
           P,V,T, P2,V2,T2
        """

        def floatOrRaise(s):
            """ Convert a floating point number, but raise an exception if the number is 'nan' """

            s = s.lower()
            if s == 'nan':
                raise ValueError('NaN is not acceptable here.')

            return float(s)
        
        cvtPos = res.KVs.get('ConvPos', None)

        if not res.ok or cvtPos == None:
            CPL.log('GuideLoop', 'no coordinate conversion (ok=%s)' % (res.ok))
            raise RuntimeError('not tracking the sky')
        else:
            try:
                cvtPos = map(floatOrRaise, cvtPos)
            except Exception, e:
                CPL.log('GuideLoop', 'no coordinate conversion (ok=%s)' % (res.ok))
                raise RuntimeError('not tracking the sky')

        CPL.log("extractCnvPos", "cvtPos=%s" % (cvtPos))

        return cvtPos

    def _checkCoordinates(self, pos):
        """ Check whether pos is a valid pair of valid coordinates. """

        if "%s" % pos[0] == 'nan' or "%s" % pos[1] == 'nan':
            self.interestedParty.failGuiding('cannot convert undefined coordinates')
            
    def pixels2inst(self, pos):
        """ convert from pixels to degrees on the instrument plane """
        # (pos - centPix) / pix/deg

        instPos = ((pos[0] - self.boresight[0]) / self.imScale[0], \
                   (pos[1] - self.boresight[1]) / self.imScale[1])

        return instPos
    
    def inst2pixels(self, pos):
        """ convert from degrees to pixels on the instrument plane """
        # (pos * pix/deg) + ctrPix

        pixel = ((pos[0] * self.imScale[0]) + self.boresight[0],
                 (pos[1] * self.imScale[1]) + self.boresight[1])

        return pixel
    
    def frame2ICRS(self, pos):
        """ Convert a Guide frame coordinate to an ICRS coordinate. """        

        if self.frameName == 'inst':
            pos = self.pixels2inst(pos)
            
        # self.cmd.respond('debug=%s' % (CPL.qstr("gpos2ICRS pos=%r" % (pos,))))

        self._checkCoordinates(pos)
        ret = client.call("tcc", "convert %0.5f,%0.5f %s icrs" % \
                          (pos[0], pos[1], self.frameName),
                          cid=self.interestedParty.controller.cidForCmd(self.interestedParty.cmd))
        return self._extractCnvPos(ret)
    
    def frame2Obs(self, pos):
        """ Convert a Guide frame coordinate pair to an Observed coordinate pair.

        Args:
            pos   - pos1,pos2

        Returns:
            cvtpos1, cvtpos2
        """

        if self.frameName == 'inst':
            pos = self.pixels2inst(pos)
            
        # self.cmd.respond('debug=%s' % (CPL.qstr("gpos2Obs pos=%r" % (pos,))))        
        self._checkCoordinates(pos)

        ret = client.call("tcc", "convert %0.5f,%0.5f %s obs" % \
                          (pos[0], pos[1], self.frameName),
                          cid=self.interestedParty.controller.cidForCmd(self.interestedParty.cmd))
        return self._extractCnvPos(ret)
    
    def _ICRS2Obs(self, pos):
        """ Convert an ICRS coordinate to an Observed coordinate. """

        # self.cmd.respond('debug=%s' % (CPL.qstr("ICRS2Obs pos=%r" % (pos,))))        
        self._checkCoordinates(pos)

        ret = client.call("tcc", "convert %0.5f,%0.5f icrs obs" % \
                          (pos[0], pos[1]),
                          cid=self.interestedParty.controller.cidForCmd(self.interestedParty.cmd))
        return self._extractCnvPos(ret)

    def ICRS2Frame(self, pos):
        """ Convert an ICRS coordinate to a guider frame coordinate. """

        # self.cmd.respond('debug=%s' % (CPL.qstr("ICRS2Frame pos=%r" % (pos,))))        
        self._checkCoordinates(pos)

        ret = client.call("tcc", "convert %0.5f,%0.5f icrs %s" % \
                          (pos[0], pos[1], self.frameName),
                          cid=self.interestedParty.controller.cidForCmd(self.interestedParty.cmd))
        return self._extractCnvPos(ret)
