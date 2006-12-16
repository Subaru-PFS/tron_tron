__all__ = ['fits']

import math
import os
import tempfile
import time

import g
import hub
import CPL
import Parsing
from RO.Alg import OrderedDict
from Hub.KV.KVDict import *
import Misc.FITS
from Misc.FITS.Cards import *
import Vocab.InternalCmd as InternalCmd

class fits(InternalCmd.InternalCmd):
    """ All the commands that the "fits" package provides. To wit:

    fits start inst=INST [out=FILENAME] [time=TIME] [args]
    fits finish inst=INST [in=FILENAME] [out=FILENAME] [time=TIME] [args]

    Much of the meat happens in per-instrument subclasses.
    """
    
    def __init__(self, **argv):
        InternalCmd.InternalCmd.__init__(self, 'fits', **argv)
        self.debug = argv.get('debug', 0)
        self.commands = { 'start' : self.start,
                          'finish' : self.finish,
                          'abort' : self.abort,
                          'status' : self.status
                          }
        # FITS
        self.headers = {}

        self.instClasses = { 'echelle' : echelleFITS,
                             'dis' : disFITS,
                             'nicfps' : nicfpsFITS,
                             'ecam' : guiderFITS,
                             'gcam' : guiderFITS,
                             'dcam' : guiderFITS,
                             }

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

    def abort(self, cmd):
        """ Remove all traces of a given instrument's header and file. """

        raise NotImplementedError("abort")
        
    def start(self, cmd):
        """ Reserve a fits header for a given instrument. Optionally create the output file.


        CmdArgs:
           inst         - name of the instrument.

        OptCmdArgs:
           comment=     - comment string
           infile=      - filename to read FITS data from
           outfile=     - filename to create. Fail if it cannot be created.
        """

        matched, unmatched, leftovers = cmd.match([('start', None),
                                                   ('comment', Parsing.dequote),
                                                   ('outfile', Parsing.dequote)])
        if len(leftovers) != 1:
            cmd.fail('hubTxt="usage: fits start INSTname [comment=COMMENT] [outfile=FILENAME]"')
            return

        inst = leftovers.keys()[0].lower()
        instClass = self.getInst(cmd, inst)
        if not instClass:
            cmd.fail('hubTxt="unknown instrument: %s"' % (inst))
            return

        if inst in self.headers:
            cmd.warn('hubTxt="Overwriting header for %s"' % (inst))

        CPL.log("fits.start", "starting header for %s" % (inst))

        comment = matched.get('comment', None)
        outfile = matched.get('outfile', None)

        self.headers[inst] = instClass(inst, cmd, outfile=outfile, comment=comment)
        self.headers[inst].start(cmd)
        cmd.finish()
        
    def finish(self, cmd):
        """ Finish off a FITS file: merge all data and headers into an output file.

        CmdArgs:
           inst       - name f the instrument.

        OptCmdArgs:
           infile=    - filename to read from.
           outfile=   - filename to write from.
           inkey=     - inst keyword to use to get infile from.
           
        Notes:
           If both inkey and infile are specified, infile wins.

           This must be called after the instrument has fully read out and generated
           any header keys, but before any additional commands might have gone to the
           instrument. That could be tricky.
        """
        
        d0, words, d1 = cmd.match({})
        matched, unmatched, leftovers = cmd.match([('finish', None),
                                                   ('infile', Parsing.dequote),
                                                   ('outfile', Parsing.dequote),
                                                   ('inkey', Parsing.dequote)])
        if len(leftovers) != 1:
            cmd.fail('hubTxt="usage: fits finish INSTname [infile=FILENAME]"')
            return

        inst = leftovers.keys()[0].lower()
        if inst not in self.headers:
            cmd.fail('hubTxt="No header to finish for %s"' % (inst))
            return
        t0 = time.time()
        CPL.log("fits.finish", "finishing header for %s" % (inst))
        obj = self.headers[inst]

        inFile = matched.get('infile', None)
        inKey = matched.get('inkey', None)
        if inFile != None and inKey != None:
            cmd.warn('fitsTxt="Both infile and inkey were specified. Using infile"')
            inKey = None

        if inKey != None:
            inFile = g.KVs.getKey(inst, inKey, None)
        outFile = matched.get('outfile', None)
        
        obj.finish(cmd, inFile, outFile=outFile)

        t1 = time.time()
        CPL.log("fits.finish", "finished header for %s in %0.2fs" % (inst, t1-t0))

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

    def __init__(self, instName, cmd, **argv):
        self.instName = instName
        self.cmd = cmd
        self.debug = argv.get('debug', 0)
        self.cards = OrderedDict()
        self.comment = argv.get('comment', None)
        # cmd.warn('debug=%s' % (CPL.qstr('InstFITS args = %s; comment=%s' % (argv, self.comment))))
        
        self.outfileName = argv.get('outfile', None)
        self.infile = None
        self.outfile = None
        self.allowOverwrite = argv.get('alwaysAllowOverwrite', False)
        
        self.isImager = False
        self.WCS = None
        
        if self.outfileName:
            self.createOutfile(cmd, self.outfileName)
            
    def TS(self, t, format="%Y-%m-%d %H:%M:%S", zone="", goodTo=2):
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
        
        
    def getCardAs(self, cmd, cardName, src, keyName, cnv, CardType, comment, idx=None):
        """ Return a new fully-fleshed out card.

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
            card = CardType(cardName, cnvV, comment)
        except:
            cmd.warn('fitsTxt="%s: could not create the %s FITS card"' % (self.instName, cardName))
                     
        CPL.log("fits", "card %s: name %s=%s" % (cardName, keyName, cnvV))

        return card
    
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
        """ Append a single FITS card to cards.
        """

        self.cards[card.name] = card
        
    def fetchSiteCards(self, cmd):
        """ Return the static cards which define the site, """

        cards = []
        cards.append(StringCard('OBSERVAT', 'APO', 'Per the IRAF observatory list.'))
        cards.append(StringCard('TELESCOP', '3.5m'))
        cards.append(StringCard('INSTRUME', self.instName, 'Instrument name'))
        cards.append(RealCard('LATITUDE', 32.780361, 'Latitude of telescope base'))
        cards.append(RealCard('LONGITUD', -105.820417, 'Longitude of telescope base'))

        return cards

    def fetchWeatherCards(self, cmd):
        self.fetchCardAs(cmd, 'AIRPRESS', 'tcc', 'Pressure', asFloat, RealCard, 'Air pressure, Pascals')
        self.fetchCardAs(cmd, 'HUMIDITY', 'tcc', 'Humidity', asFloat, RealCard, 'Humidity, fraction')

    def fetchTelescopeCards(self, cmd):
        k = g.KVs.getKey('tcc', 'AxePos', [0.0,0.0,0.0])
        k = map(float, k)
        alt = k[1]
        zd = 90.0 - alt
        try:
            airmass = 1.0/math.cos((zd / 180.0) * math.pi)
        except:
            airmass = 0.0
                
        self.fetchCardAs(cmd, 'TELAZ', 'tcc', 'AxePos', asFloat, RealCard, 'TCC AxePos azimuth', idx=0)
        self.fetchCardAs(cmd, 'TELALT', 'tcc', 'AxePos', asFloat, RealCard, 'TCC AxePos altitude', idx=1)
        self.fetchCardAs(cmd, 'TELROT', 'tcc', 'AxePos', asFloat, RealCard, 'TCC AxePos rotator', idx=2)
        self.fetchCardAs(cmd, 'TELFOCUS', 'tcc', 'SecFocus', asFloat, RealCard, 'TCC SecFocus')
        self.appendCard(cmd, RealCard('ZD', zd, 'Zenith distance'))
        self.appendCard(cmd, RealCard('AIRMASS', airmass, '1/cos(ZD)'))
        
        self.fetchCardAs(cmd, 'BOREOFFX', 'tcc', 'Boresight', asFloat, RealCard, 'TCC boresight offset X', idx=0)
        self.fetchCardAs(cmd, 'BOREOFFY', 'tcc', 'Boresight', asFloat, RealCard, 'TCC boresight offset Y', idx=3)

    def fetchWCSInfo(self, cmd):
        """ Gather TCC inputs for WCS cards. Requires that we be tracking.
        """

        # fetch instrument scale
        k = g.KVs.getKey('tcc', 'IImScale', [1.0,1.0])
        imScale = map(float, k)
        
        # and center
        k = g.KVs.getKey('tcc', 'IImCtr', [123.0,123.0])
        imCtr = map(float, k)
        
        # instrument angle w.r.t. sky
        k = g.KVs.getKey('tcc', 'ObjInstAng', [0.0,0.0,0.0])
        if 'NaN' in k:
            return
        
        k = map(float, k)
        instAng = (k[0] / 180.0) * math.pi

        # and boresight offset
        k = g.KVs.getKey('tcc', 'Boresight', [0.0,0.0,0.0,0.0,0.0,0.0])
        k = map(float, k)
        boresight = k[0], k[3]

        # RA * dec
        k = g.KVs.getKey('tcc', 'ObjNetPos', [0.0,0.0,0.0,0.0,0.0,0.0])
        k = map(float, k)
        ra, dec = k[0], k[3]

        self.WCS = { 'imScale'   : imScale,
                     'imCtr'     : imCtr,
                     'instAng'   : instAng,
                     'boresight' : boresight,
                     'ra'        : ra,
                     'dec'       : dec }
        
    def addWCSCards(self, cmd, fits):
        """ Add WCS cards to ourselves. Requires that we be tracking.
        """

        if not self.WCS:
            return

        # Convert from unbinned full-frame to binned subframe
        #
        binx = fits.cards.get('BINX', 1)
        biny = fits.cards.get('BINY', 1)
        begx = fits.cards.get('BEGX', 1.0)
        begy = fits.cards.get('BEGY', 1.0)

        imCtr = self.WCS['imCtr']
        imScale = self.WCS['imScale']
        boresight = self.WCS['boresight']
        instAng = self.WCS['instAng']

        imScale[0] /= binx
        imScale[1] /= biny
        imCtr[0] = imCtr[0] / binx - (begx-1)
        imCtr[1] = imCtr[1] / biny - (begy-1)
        
        self.appendCard(cmd, StringCard('CTYPE1', 'RA---TAN', 'WCS projection'))
        self.appendCard(cmd, StringCard('CTYPE2', 'DEC--TAN', 'WCS projection'))
        
        self.appendCard(cmd, RealCard('CRPIX1', imCtr[0] + boresight[0] * imScale[0], 'WCS reference pixel'))
        self.appendCard(cmd, RealCard('CRPIX2', imCtr[1] + boresight[1] * imScale[1], 'WCS reference pixel'))
                        
        self.appendCard(cmd, RealCard('CRVAL1', self.WCS['ra'], 'WCS reference sky pos.'))
        self.appendCard(cmd, RealCard('CRVAL2', self.WCS['dec'], 'WCS reference sky pos.'))
                        
        self.appendCard(cmd, RealCard('CD1_1', (1.0 / imScale[0]) * math.cos(instAng),
                                      'WCS (1/InstScaleX)*cos(InstAng)'))
        self.appendCard(cmd, RealCard('CD1_2', (1.0 / imScale[1]) * math.sin(instAng),
                                      'WCS (1/InstScaleY)*sin(InstAng)'))
        self.appendCard(cmd, RealCard('CD2_1', -(1.0 / imScale[0]) * math.sin(instAng),
                                      'WCS (-1/(InstScaleX)*sin(InstAng)'))
        self.appendCard(cmd, RealCard('CD2_2', (1.0 / imScale[1]) * math.cos(instAng),
                                      'WCS (1/InstScaleY)*cos(InstAng)'))
        
    def fetchObjectCards(self, cmd):
        objSys = g.KVs.getKey('tcc', 'ObjSys', None)
        csys = 'Unknown'
        if objSys != None:
            csys = objSys[0]
            
        tracking = csys not in ('Mount', 'Physical', 'Unknown', 'None')
        
        self.fetchCardAs(cmd, 'OBJNAME', 'tcc', 'ObjName',
                         asDeQStr, StringCard, 'Object name, per TCC ObjName')

        # self.appendCard(cmd, CommentCard('COMMENT', 'All coordinates and offsets are from the start of the exposure'))
        
        self.fetchCardAs(cmd, 'RADECSYS', 'tcc', 'ObjSys',
                         asStr, StringCard, 'Coordinate system, per TCC ObjSys', idx=0)
        self.fetchCardAs(cmd, 'ROTTYPE', 'tcc', 'RotType',
                         asFloat, StringCard, 'TCC RotType')
        self.fetchCardAs(cmd, 'ROTPOS', 'tcc', 'RotPos',
                         asFloat, RealCard, 'User-specified rotation wrt ROTTYPE')

        if tracking:
            self.fetchCardAs(cmd, 'EQUINOX', 'tcc', 'ObjSys',
                             asFloat, RealCard, 'Equinox, per TCC ObjSys', idx=1)
            self.fetchCardAs(cmd, 'OBJANGLE', 'tcc', 'ObjInstAng',
                             asFloat, RealCard, 'Angle from inst x,y to sky', idx=0)
            self.fetchCardAs(cmd, 'RA', 'tcc', 'ObjPos',
                             asRASex, StringCard, 'RA hours, from TCC ObjNetPos', idx=0)
            self.fetchCardAs(cmd, 'DEC', 'tcc', 'ObjPos',
                             asDecSex, StringCard, 'Dec degrees, from TCC ObjNetPos', idx=3)

            try:
                lst = float(g.KVs.getKey('tcc', 'LST')) / 15.0
                self.appendCard(cmd, RealCard('LST', lst, 'Local Mean Sidereal time, hours'))
            except:
                pass
            
            self.fetchCardAs(cmd, 'ARCOFFX', 'tcc', 'ObjArcOff',
                             asFloat, RealCard, 'TCC arc offset X', idx=0)
            self.fetchCardAs(cmd, 'ARCOFFY', 'tcc', 'ObjArcOff',
                             asFloat, RealCard, 'TCC arc offset Y', idx=3)
            self.fetchCardAs(cmd, 'OBJOFFX', 'tcc', 'ObjOff',
                             asFloat, RealCard, 'TCC object offset X', idx=0)
            self.fetchCardAs(cmd, 'OBJOFFY', 'tcc', 'ObjOff',
                             asFloat, RealCard, 'TCC object offset Y', idx=3)
            self.fetchCardAs(cmd, 'CALOFFX', 'tcc', 'CalibOff',
                             asFloat, RealCard, 'TCC calibration offset X', idx=0)
            self.fetchCardAs(cmd, 'CALOFFY', 'tcc', 'CalibOff',
                             asFloat, RealCard, 'TCC calibration offset Y', idx=3)
            self.fetchCardAs(cmd, 'BOREOFFX', 'tcc', 'Boresight',
                             asFloat, RealCard, 'TCC boresight offset X', idx=0)
            self.fetchCardAs(cmd, 'BOREOFFY', 'tcc', 'Boresight',
                             asFloat, RealCard, 'TCC boresight offset Y', idx=3)
            

    def _setUTC_TAI(self, cmd):
        """ Note the current UTC-TAI offset.
        """

        UTC_TAI = self.fetchValueAs(cmd, 'tcc', 'UTC_TAI', float)
        if UTC_TAI == None:
            UTC_TAI = -33.0

        self.UTC_TAI = UTC_TAI
        
    def start(self, cmd, inFile=None):
        self._setUTC_TAI(cmd)
        if self.isImager:
            try:
                self.fetchWCSInfo(cmd)
            except Exception, e:
                cmd.warn('errorTxt=%s' % (CPL.qstr("Failed to get WCS info: %s" % (e))))
        self.fetchObjectCards(cmd)
        self.fetchWeatherCards(cmd)
        self.fetchTelescopeCards(cmd)

    def fetchTimeCards(self, cmd):
        return []
    
    def finish(self, cmd, inFile, outFile=None):

        self.fetchInstCards(cmd)
        if inFile == None:
            cmd.fail('fitsTxt=%s' % (CPL.qstr("NO IMAGE FILE FOR %s!!!!" % (self.instName))))
            return
        try:
            inFITS = Misc.FITS.FITS(inputFile=inFile, alwaysAllowOverwrite=self.allowOverwrite)
        except Exception, e:
            cmd.fail('fitsTxt=%s' % (CPL.qstr("Could not read FITS file %s: %s" % (inFile, e))))
            return False

        if outFile:
            self.outfileName = outFile
            self.outfile = open(self.outfileName, "w+")
            
        self.finishHeader(cmd, inFITS)

    def prepFITS(self, cmd, fits):
        """ Hook to let us fiddle with the header directly. """
        pass
    
    def fetchInstCards(self, cmd):
        """ Hook to let us fiddle with the instrument cards directly. """
        pass
    
    def finishHeader(self, cmd, fits):
        """ Finish off a given FITS header by adding our keys, then writing out a new file.

        Args:
            cmd     - the controlling Command.
            fits    - a FITS object.
        """

        self.prepFITS(cmd, fits)
        
        siteCards = self.fetchSiteCards(cmd)
        timeCards = self.fetchTimeCards(cmd)
        try:
            self.addWCSCards(cmd, fits)
        except Exception, e:
            cmd.warn('errorTxt=%s' % (CPL.qstr("Failed to generate WCS cards: %s" % (e))))

        cmd.inform('fitsDebug=%s' % (CPL.qstr("Generating fits file %s" % (self.outfileName))))

        # Stuff the header with our cards. Stick them at the top of the header.
        after = 'NAXIS2'

        # Site cards first
        for c in siteCards:
            fits.addCard(c, after=after, allowOverwrite=True)
            after = c.name

        # Time cards next
        for c in timeCards:
            fits.addCard(c, after=after)
            after = c.name

        # Then the rest
        for c in self.cards.itervalues():
            fits.addCard(c, after=after)
            after = c.name

        if self.comment != None:
            fits.addCard(CommentCard('COMMENT', self.comment), after='NAXIS2')

        if self.outfile == None:
            self.outfile, self.outfileName = tempfile.mkstemp('.fits', "%s-" % (self.instName),
                                                              '/export/images')
            cmd.warn('fitsTxt=%s' % \
                     (CPL.qstr("BAD NEWS: no filename specified for fits start or finish. Saving to %s" % \
                               (self.outfileName))))
            
        cmd.inform('fitsDebug=%s' % (CPL.qstr("Writing fits file %s" % (self.outfileName))))
        fits.writeToFile(self.outfile)
        self.outfile.close()
        del fits

        cmd.finish('fitsTxt=%s' % \
                   (CPL.qstr("Finished writing the %s file: %s" % (self.instName, self.outfileName))))

    def createOutfile(self, cmd, filename):
        """ Actually create the output file.

        Args:
           cmd      - the controlling Command
           filename - the filename to use.

        Returns:
            boolean  - whether we succeeded.
            
        self.file and self.filename will be modified. Note that self.file already exists, we warn but do not
        fail. The point is that .createFile will only be called before any significant data is written. So changing
        .file should not have us lose any data.

        """

        if self.outfile != None:
            cmd.warn('fitsTxt=%s' % (CPL.qstr("fits.creatFile is overwriting its file.")))
        if self.outfileName != None:
            cmd.warn('fitsTxt=%s' % (CPL.qstr("fits.creatFile is overwriting its file. old filename=%s, new filename=%s" % \
                                              (self.outfileName, filename))))
            
        try:
            f = os.open(filename, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0664)
            fd = os.fdopen(f, "w")
            CPL.log('InstFITS.createFile', 'filename=%s' % (filename))
        except (OSError, IOError), e:
            cmd.fail('fitsTxt=%s' % \
                     (CPL.qstr("Could not create %s (%s)" % (filename, e.strerror))))
            return False

        self.outfile = fd
        self.outfileName = filename

        return True
        
    def baseTimeCards(self, cmd, expStart, expLength, goodTo=0.1):
        """ Return the core time cards.

        Args:
           cmd       - the controlling Command.
           expStart  - the start of the exposure, TAI
           expLength - the length of the exposure, seconds.
           goodTo    - the precision of the timestamps.
        """

        cards = []
        cards.append(RealCard('UTC-TAI', self.UTC_TAI, 'UTC offset from TAI, seconds.'))

        cards.append(StringCard('TIMESYS', 'TAI', 'Timebase for DATE-OBS'))
        cards.append(StringCard('DATE-OBS',
                                self.TS(expStart, format="%Y-%m-%dT%H:%M:%S", goodTo=3),
                                'Start of integration.'))

        cards.append(StringCard('UTC-OBS',
                                self.TS(expStart + self.UTC_TAI, format="%H:%M:%S", goodTo=3),
                                'Start of integration.'))
        cards.append(StringCard('UTMIDDLE',
                                self.TS(expStart + self.UTC_TAI + (expLength/2.0), format="%H:%M:%S", goodTo=3),
                                'Middle of integration.'))
        cards.append(RealCard('EXPTIME', expLength, 'Exposure time, seconds'))

        return cards
    
    def fetchTimeCards(self, cmd):

        # Calculate Unix time for the beginning of the exposure.
        #
        #time_s = self.fetchValueAs(cmd, 'grim', 'STARTTIME', str)
        #date_s = self.fetchValueAs(cmd, 'grim', 'STARTDATE', str)
        #opentime = self.fetchValueAs(cmd, 'grim', 'OPENTIME', float)
        #if time_s == None or date_s == None:
        #    return

        #dt_s = "%s %s" % (date_s, time_s)
        #utcExpStart = time.mktime(time.strptime(dt_s, "%m/%d/%Y %H:%M:%S")) - time.timezone

        utcExpStart = time.time()
        opentime = 0.0
        cards = self.baseTimeCards(cmd, utcExpStart - self.UTC_TAI, opentime)
        return cards
    
class nicfpsFITS(InstFITS):
    """ The NICFPS-specific FITS routines.
    """

    def __init__(self, instName, cmd, **argv):
        argv['alwaysAllowOverwrite'] = True
        InstFITS.__init__(self, instName, cmd, **argv)

        # Request WCS cards.
        self.isImager = True
        
    def start(self, cmd, inFile=None):
        InstFITS.start(self, cmd, inFile=inFile)
        
        self.fetchInstCards(cmd)

    def baseTimeCards(self, cmd, expStart, expLength, goodTo=0.1):
        """ Return the core time cards.

        Args:
           cmd       - the controlling Command.
           expStart  - the start of the exposure, TAI
           expLength - the length of the exposure, seconds.
           goodTo    - the precision of the timestamps.
        """

        cards = []
        cards.append(RealCard('UTC-TAI', self.UTC_TAI, 'UTC offset from TAI, seconds.'))

        return cards
    
class echelleFITS(InstFITS):
    """ The Echelle-specific FITS routines.
    """

    def __init__(self, instName, cmd, **argv):
        argv['alwaysAllowOverwrite'] = True
        InstFITS.__init__(self, instName, cmd, **argv)
        
    def baseTimeCards(self, cmd, expStart, expLength, goodTo=0.1):
        """ Return the core time cards.

        Args:
           cmd       - the controlling Command.
           expStart  - the start of the exposure, TAI
           expLength - the length of the exposure, seconds.
           goodTo    - the precision of the timestamps.
        """

        cards = []
        cards.append(RealCard('UTC-TAI', self.UTC_TAI, 'UTC offset from TAI, seconds.'))

        return cards
    
class disFITS(InstFITS):
    """ The Dis-specific FITS routines.
    """

    def __init__(self, instName, cmd, **argv):
        argv['alwaysAllowOverwrite'] = True
        InstFITS.__init__(self, instName, cmd, **argv)
        
    def baseTimeCards(self, cmd, expStart, expLength, goodTo=0.1):
        """ Return the core time cards.

        Args:
           cmd       - the controlling Command.
           expStart  - the start of the exposure, TAI
           expLength - the length of the exposure, seconds.
           goodTo    - the precision of the timestamps.
        """

        cards = []
        cards.append(RealCard('UTC-TAI', self.UTC_TAI, 'UTC offset from TAI, seconds.'))

        return cards
    
class guiderFITS(InstFITS):
    """ The guider specific FITS routines.
    """

    def __init__(self, instName, cmd, **argv):
        argv['alwaysAllowOverwrite'] = True
        InstFITS.__init__(self, instName, cmd, **argv)

        # Hack out the gcam WCS cards, since I don't know how to
        # get the equivalent of ObjNetPos.
        #
        if instName != 'gcam':
            self.isImager = True
            
    def baseTimeCards(self, cmd, expStart, expLength, goodTo=0.1):
        """ Return the core time cards.

        Args:
           cmd       - the controlling Command.
           expStart  - the start of the exposure, TAI
           expLength - the length of the exposure, seconds.
           goodTo    - the precision of the timestamps.
        """

        cards = []
        cards.append(RealCard('UTC-TAI', self.UTC_TAI, 'UTC offset from TAI, seconds.'))

        return cards
