__all__ = ['fits']

import math
import os
import time

import g
import hub
import CPL
import Parsing
from RO.Alg.OrderedDict import OrderedDict
from Hub.KV.KVDict import *
from Misc.FITS import *
import Vocab.InternalCmd as InternalCmd

class fits(InternalCmd.InternalCmd):
    """ All the commands that the "fits" package provides. To wit:

    fits start inst=INST [time=TIME] [args]
    fits finish inst=INST in=FILENAME out=FILENAME [time=TIME] [args]

    For GRIm and the Echelle,
    """
    
    def __init__(self, **argv):
        InternalCmd.InternalCmd.__init__(self, 'fits', **argv)
        self.debug = argv.get('debug', 0)
        self.commands = { 'start' : self.start,
                          'finish' : self.finish,
                          'status' : self.status
                          }
        # FITS
        self.headers = {}

        self.instClasses = { 'grim' : grimFITS,
                             'echelle' : echelleFITS,
                             'dis' : disFITS }
        
    def getInst(self, cmd, inst):
        """ Return the instrument object, or fail the command. """

        if inst not in self.instClasses:
            cmd.fail('hubTxt=%s' % (CPL.qstr("Unknown instrument: %s" % inst)))
            return None
            
        return self.instClasses[inst]

    def status(self, cmd):
        """ List our active headers. """

        for h in self.headers.keys():
            cmd.inform('fitsTxt="header for %s"' % (self.headers[h].instName))
        cmd.finish('')
        
    def start(self, cmd):
        """
        """

        # Switch to real parsing, Craig.
        d0, words, d1 = cmd.match({})
        words = d1.keys()
        CPL.log("fits.start", "args(%d)=%s" % (len(words), words))
        
        if len(words) < 2 or len(words) > 4:
            cmd.fail('hubTxt="usage: fits start INSTname [comment]"')
            return

        inst = words[1].lower()
        instClass = self.getInst(cmd, inst)
        if not instClass:
            cmd.fail('hubTxt="unknown instrument: %s"' % (inst))
            return

        if inst in self.headers:
            cmd.warn('hubTxt="Overwriting header for %s"' % (inst))

        CPL.log("fits.start", "starting header for %s" % (inst))

        self.headers[inst] = instClass(cmd)
        self.headers[inst].start(cmd)
        
    def finish(self, cmd):
        """ Finish off a FITS file: merge all data and headers into an output file.

        Note:
           This must be called after the instrument has fully read out and generated
           any header keys, but before any additional commands might have gone to the
           instrument. That could be tricky.
        """
        
        d0, words, d1 = cmd.match({})
        words = d1.keys()
        if len(words) != 3:
            cmd.fail('hubTxt="usage: fits finish INSTname outFile"')
            return
        
        inst = words[1].lower()
        outFile = Parsing.dequote(words[2])
        
        if inst not in self.headers:
            cmd.fail('hubTxt="No header to finish for %s"' % (inst))
            return

        obj = self.headers[inst]
        obj.finish(cmd, outFile)

        del self.headers[inst]
        
########
#
# Implement some type converters here, because we may need to handle default and error values
# differently from non-FITS creators.
#
########

def asStr(s, default='unknown'):
    if s == None:
        raise ValueError('value could not be converted')
        return default
    return s

def asDeQStr(s, default='unknown'):
    if s == None:
        raise ValueError('value could not be converted')
        return default
    return asStr(Parsing.dequote(s))

def asInt(s, default=-99999999):
    if s == None or s == 'NaN':
        raise ValueError('value could not be converted')
        return default
    try:
        i = int(s)
    except Exception, e:
        raise ValueError('value could not be converted')
        i = default

    return i

def asFloat(s, default=-99999999.0):
    if s == None or s == 'NaN':
        raise ValueError('value could not be converted')
        return default
    try:
        f = float(s)
    except Exception, e:
        raise ValueError('value could not be converted')
        f = default

    return f

def asFraction(s, default=0.0):
    if s == None or s == 'NaN':
        raise ValueError('value could not be converted')
        return default
    try:
        f = float(s)
    except Exception, e:
        raise ValueError('value could not be converted')
        f = default

    return f * 100.0

def asRASex(s, default='unknown'):
    if s == None:
        raise ValueError('value could not be converted')

    dr = float(s)
    rah = int(dr/15.0)
    ram = int(4.0 * (dr - 15.0 * rah))
    ras = 240 * (dr - 15 * rah - ram/4.0)
    
    return "%d:%02d:%05.2f" % (rah, ram, ras)

def asDecSex(s, default='unknown'):
    if s == None:
        raise ValueError('value could not be converted')

    dd = float(s)

    if dd < 0:
        sign = '-'
        dd = -dd
    else:
        sign = ''
        
    ded = int(dd)
    dem = int((dd - ded) * 60)
    des = 3600.0 * (dd - ded - dem/60.0)
    
    return "%s%d:%02d:%05.2f" % (sign, ded, dem, des)

class InstFITS(object):
    """ The common FITS routines.
    """

    def __init__(self, cmd, **argv):
        self.cmd = cmd
        self.debug = argv.get('debug', 0)
        self.cards = OrderedDict()
        self.instName = "unknown"
        
    def fetchValueAs(self, cmd, src, keyName, cnv, idx=None):
        """ Fetch and convert a keyword value. """
        
        v = g.KVs.getKey(src, keyName, None)
        if idx != None:
            try:
                v = v[idx]
            except:
                v = None

        # Treat conversion errors as hints that we should not include the data...
        try:
            cnvV = cnv(v)
        except:
            CPL.log("fits", "value %s for %s.%s did not convert" % (v, src, keyName))
            return None

        return cnvV
        
        
    def fetchCardAs(self, cmd, cardName, src, keyName, cnv, CardType, comment, idx=None):
        """ Append a new fully-fleshed out card.

        Args:
          cmd        - the Command which might care about good/bad news.
          cardName   - the FITS card name.
          src        - who has the key?
          keyName    - and what is it called?
          cnv        - how to convert it?
          CardType   - The FITS Card type.
          comment    - a FITS comment
          idx        ? The index into the value array of the value we want.
        """

        cnvV = self.fetchValueAs(cmd, src, keyName, cnv, idx=idx)
        if cnvV == None:
            return
        
        try:
            self.cards[cardName] = CardType(cardName, cnvV, comment)
        except:
            cmd.warn('fitsTxt="%s: could not create the %s FITS card"' % (self.instName, cardName))
                     
        CPL.log("fits", "card %s: name %s=%s" % (cardName, keyName, cnvV))
                
    def appendCard(self, cmd, card):
        """ Append a FITS card.
        """

        self.cards[card.name] = card
        
    def returnSiteCards(self, cmd):
        """ Return the static cards which define the site, """

        cards = []
        cards.append(StringCard('OBSERVAT', 'APO', 'Per the IRAF observatory list.'))
        cards.append(StringCard('TELESCOP', '3.5m'))
        cards.append(RealCard('LATITUDE', 32.780361, 'Latitude of telescope base'))
        cards.append(RealCard('LONGITUD', -105.820417, 'Longitude of telescope base'))

        return cards

    def fetchWeatherCards(self, cmd):
        self.fetchCardAs(cmd, 'AIRPRESS', 'tcc', 'Pressure', asFloat, RealCard, 'Air pressure, Pascals')
        self.fetchCardAs(cmd, 'HUMIDITY', 'tcc', 'Humidity', asFloat, RealCard, 'Humidity, fraction')

    def fetchTelescopeCards(self, cmd):
        self.fetchCardAs(cmd, 'TELAZ', 'tcc', 'AxePos', asFloat, RealCard, 'TCC AxePos azimuth', idx=0)
        self.fetchCardAs(cmd, 'TELALT', 'tcc', 'AxePos', asFloat, RealCard, 'TCC AxePos altitude', idx=1)
        self.fetchCardAs(cmd, 'TELROT', 'tcc', 'AxePos', asFloat, RealCard, 'TCC AxePos rotator', idx=2)
        self.fetchCardAs(cmd, 'TELFOCUS', 'tcc', 'SecFocus', asFloat, RealCard, 'TCC SecFocus')
    
    def fetchObjectCards(self, cmd):
        objSys = g.KVs.getKey('tcc', 'ObjSys', None)
        csys = 'Unknown'
        if objSys != None:
            csys = objSys[0]
            
        tracking = csys not in ('Mount', 'Physical', 'Unknown', 'None')
        
        self.fetchCardAs(cmd, 'OBJNAME', 'tcc', 'ObjName', asDeQStr, StringCard, 'Object name, per TCC ObjName')
        
        self.fetchCardAs(cmd, 'RADECSYS', 'tcc', 'ObjSys', asStr, StringCard, 'Coordinate system, per TCC ObjSys', idx=0)
        if tracking:
            self.fetchCardAs(cmd, 'EQUINOX', 'tcc', 'ObjSys', asFloat, RealCard, 'Equinox, per TCC ObjSys', idx=1)
            self.fetchCardAs(cmd, 'OBJANGLE', 'tcc', 'ObjInstAng', asFloat, RealCard, 'Angle from inst x,y to sky', idx=0)
            self.fetchCardAs(cmd, 'RA', 'tcc', 'ObjNetPos', asRASex, StringCard, 'RA hours, from TCC ObjNetPos', idx=0)
            self.fetchCardAs(cmd, 'DEC', 'tcc', 'ObjNetPos', asDecSex, StringCard, 'Dec degrees, from TCC ObjNetPos', idx=3)
        self.fetchCardAs(cmd, 'ROTTYPE', 'tcc', 'RotType', asFloat, StringCard, 'TCC RotType')
        self.fetchCardAs(cmd, 'ROTPOS', 'tcc', 'RotPos', asFloat, RealCard, 'User-specified rotation wrt ROTTYPE')
    
    def _setUTC_TAI(self, cmd):
        """ Note the current UTC-TAI offset.
        """

        UTC_TAI = self.fetchValueAs(cmd, 'tcc', 'UTC_TAI', float)
        if UTC_TAI == None:
            UTC_TAI = -32.0

        self.UTC_TAI = UTC_TAI
        
    def start(self, cmd, inFile):
        self._setUTC_TAI(cmd)
        self.fetchObjectCards(cmd)
        self.fetchWeatherCards(cmd)
        self.fetchTelescopeCards(cmd)

    def generateTimeCards(self, cmd):
        return []
    
    def finish(self, cmd, outName):
        """ Finish off a FITS file by reading in a given file, adding our keys, then writing out a new file.

        Args:
          outFile  - the name of the output file. Must not exist.
        """

        siteCards = self.returnSiteCards(cmd)
        timeCards = self.generateTimeCards(cmd)

        scratchFile = g.KVs.getKey(self.instName, 'scratchFile', None)
        if scratchFile == None:
            cmd.fail('fitsTxt=%s' % (CPL.qstr("NO IMAGE FILE FOR %s!!!!" % (self.instName))))
            return

        try:
            inFITS = FITS(inputFile=scratchFile)
        except Exception, e:
            cmd.fail('fitsTxt=%s' % (CPL.qstr("Could not read FITS file %s: %s" % (scratchFile, e))))
            return

        cmd.inform('fitsDebug=%s' % (CPL.qstr("Generating fits file %s" % (outName))))

        # Stuff the header with our cards. Stick them at the top of the header.
        after = 'NAXIS2'

        # Site cards first
        for c in siteCards:
            inFITS.addCard(c, after=after)
            after = c.name

        # Time cards next
        for c in timeCards:
            inFITS.addCard(c, after=after)
            after = c.name

        # Then the rest
        for c in self.cards.itervalues():
            inFITS.addCard(c, after=after)
            after = c.name

        # Finally, write the output file.
        #
        try:
            f = os.open(outName, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0664)
            outFile = os.fdopen(f, "w")
            CPL.log('InstFITS.finish', 'f=%s, file=%s' % (f, outFile))
        except (OSError, IOError), e:
            cmd.fail('fitsTxt=%s' % \
                     (CPL.qstr("Could not create %s (%s)" % (outName, e.strerror))))
            return

        inFITS.writeToFile(outFile)
        outFile.close()
        del inFITS

        cmd.finish('fitsTxt=%s' % \
                   (CPL.qstr("Finished writing the %s file: %s" % (self.instName, outName))))
        
class grimFITS(InstFITS):
    """ The Grim-specific FITS routines.
    """

    def __init__(self, cmd, **argv):
        InstFITS.__init__(self, cmd, **argv)
        self.instName = 'grim'
        
    def start(self, cmd, inFile=None):
        InstFITS.start(self, cmd, inFile)
        self.fetchInstCards(cmd)
        
    def fetchNiceInstCards(self, cmd):
        """ Generate gussied up, human-readable versions of the instrument state """
        pass
    
    def fetchInstCards(self, cmd):
        self.fetchNiceInstCards(cmd)
        
        self.fetchCardAs(cmd, 'FILTER1M', 'grim', 'filter1', asInt, IntCard, 'The physical position of filter wheel 1')
        self.fetchCardAs(cmd, 'FILTER2M', 'grim', 'filter2', asInt, IntCard, 'The physical position of filter wheel 2')
        self.fetchCardAs(cmd, 'LENSMOTR', 'grim', 'lens', asInt, IntCard, 'The physical position of the camera motor')
        self.fetchCardAs(cmd, 'GRISMMOT', 'grim', 'grism', asInt, IntCard, 'The physical position of the grism motor')
        self.fetchCardAs(cmd, 'SLITMOTR', 'grim', 'slit', asInt, IntCard, 'The physical position of the slit motor')

    def TS(self, t, format="%Y-%m-%d %H:%M:%S", zone="", goodTo=1):
        """ Return a formatted timestamp for t

        Args:
           t       - seconds.
           format  - the strftime format string for the integral seconds.
           zone    - an optional ISO marker for the end of the string
           goodTo  - how precise the timestamp is. 10e-goodTo seconds. Must be >= 0
        """

        if zone == None:
            zone = ''

        # Parts:
        #  - the to-a-second timestamp
        #
        iSecs = time.strftime(format, time.gmtime(t))

        # The fractional seconds.
        #
        if goodTo <= 0:
            fSecs = ""
        else:
            fSecsFmt = ".%%0%dd" % (goodTo)
            multiple = 10 ** goodTo
            fSecs = fSecsFmt % ((10 ** goodTo) * math.modf(t)[0])

        # Add it all up:
        #
        return "%s%s%s" % (iSecs, fSecs, zone)
    
    def baseTimeCards(self, cmd, expStart, expLength, goodTo=0.1):
        """ Return the core time cards.

        Args:
           cmd       - the controlling Command.
           expStart  - the start of the exposure, TAI
           expLength - the length of the exposure, seconds.
           goodTo    - the precision of the timestamps.
        """

        cards = []

        cards.append(StringCard('TIMESYS', 'TAI', 'Timebase for DATE-OBS'))
        cards.append(StringCard('DATE-OBS',
                                self.TS(expStart, format="%Y-%m-%dT%H:%M:%S", goodTo=3),
                                'Start of integration.'))

        cards.append(RealCard('UTC_TAI', self.UTC_TAI, 'UTC offset from TAI, seconds.'))
        cards.append(StringCard('UTC-OBS',
                                self.TS(expStart + self.UTC_TAI, format="%H:%M:%S", goodTo=3),
                                'Start of integration.'))
        cards.append(StringCard('UTMIDDLE',
                                self.TS(expStart + self.UTC_TAI + (expLength/2.0), format="%H:%M:%S", goodTo=3),
                                'Middle of integration.'))
        cards.append(RealCard('EXPTIME', expLength, 'Exposure time, seconds'))

        return cards
    
    def generateTimeCards(self, cmd):

        # Calculate Unix time for the beginning of the exposure.
        #
        time_s = self.fetchValueAs(cmd, 'grim', 'STARTTIME', str)
        date_s = self.fetchValueAs(cmd, 'grim', 'STARTDATE', str)
        opentime = self.fetchValueAs(cmd, 'grim', 'OPENTIME', float)
        if time_s == None or date_s == None:
            return

        dt_s = "%s %s" % (date_s, time_s)
        utcExpStart = time.mktime(time.strptime(dt_s, "%m/%d/%Y %H:%M:%S")) - time.timezone

        cards = self.baseTimeCards(cmd, utcExpStart - self.UTC_TAI, opentime)
        
        return cards
    
    def finish(self, cmd, outFile):
        self.fetchInstCards(cmd)
        
        InstFITS.finish(self, cmd, outFile)
        
class echelleFITS(InstFITS):
    """ The Echelle-specific FITS routines.
    """

    def __init__(self, cmd, **argv):
        InstFITS.__init__(self, cmd, **argv)
        self.instName = 'echelle'
        
    def start(self, cmd, inFile=None):
        InstFITS.start(self, cmd, inFile)
        
    def fetchInstCards(self, cmd):
        pass
    
    def finish(self, cmd, outFile):
        self.fetchInstCards(cmd)
        
        InstFITS.finish(self, cmd, outFile)

class disFITS(InstFITS):
    """ The DIS-specific FITS routines.
    """

    def __init__(self, cmd, **argv):
        InstFITS.__init__(self, cmd, **argv)
        self.instName = 'dis'
        
    def start(self, cmd, inFile=None):
        InstFITS.start(self, cmd, inFile)

    def fetchInstCards(self, cmd):
        pass
    
    def finish(self, cmd, outFile):
        self.fetchInstCards(cmd)
        
        InstFITS.finish(self, cmd, outFile)
        
