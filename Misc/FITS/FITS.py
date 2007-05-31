#!/usr/bin/env python

""" FITS.py - a very simple FITS class group.

"""

import Cards
import numarray
import pixel16

class FITS:
    """ A simple no extension image FITS file.
    
    Should be extended by turning this into a header/extension class and
    adding a multi-extension FITS class. But I don't need that (yet).
    
    We keep a list of card names (for ordering) and a dictionary of the real cards.
    Commentary cards ("COMMENT", "HISTORY", "        ") are kept in order, but given 
    scratch names to keep them distinct.


    """

    # Cards that we manage, and that cannot be added by the caller.
    # Ehh, bad idea.
    #
    standardCards = ('SIMPLE', 'BITPIX', 'NAXIS', 'NAXIS1', 'NAXIS2', 'END')

    def __init__(self, inputFile=None, lazyData=False, alwaysAllowOverwrite=False):
        self.cardOrder = []
        self.cards = {}
        self.commentIdx = 1        
        self.alwaysAllowOverwrite = alwaysAllowOverwrite
        
        self.image = None
        
        if inputFile != None:
            f = file(inputFile, "r")
            self.readFromFile(f, lazyData)
            f.close()
        
    def addCard(self, card, allowOverwrite=False, before=None, after=None):
        """ Add a single card to the FITS header. Standard headers
        cannot be added. 
        
        Args:
            card            - A FITS.*Card instance
            allowOverwrite  - Whether existing cards can be replaced.
            before          - The name of a Card that the new Card should be inserted before.
            after           - The name of a Card that the new Card should be appended after.
            
        If both before and after are specified, before wins.
        If the card for before or after does not exist, the new card is appended to the end 
        the existing header.
        """

        # Gruesome hack to keep EXTEND/EXTNAME keys from getting pushed down.
        if after == 'NAXIS2' and self.cards.has_key('EXTEND'):
            after = 'EXTEND'
        if after == 'EXTEND' and self.cards.has_key('EXTNAME'):
            after = 'EXTNAME'
            
        allowOverwrite = allowOverwrite or self.alwaysAllowOverwrite
            
        # Commentary cards get special treatment.
        name = self.getCardName(card)
        
        #if name in FITS.standardCards:
        #    raise KeyError("cannot define card named '%s'" % (name))
            
        if self.cards.has_key(name):
            if not allowOverwrite:
                raise KeyError("cannot overwrite existing card for '%s'" % (name))
            idx = self.cardOrder.index(name)
            self.cardOrder.remove(name)
            del self.cards[name]
        else:
            idx = len(self.cardOrder)
            
        
        if before != None:
            try:
                idx = self.cardOrder.index(before)
            except ValueError, e:
                pass
        elif after != None:
            try:
                idx = self.cardOrder.index(after)
                idx += 1
            except ValueError, e:
                pass
                 
        self.cardOrder.insert(idx, name)
        self.cards[name] = card
            
    def deleteCard(self, name):
        """ Try deleting a given card name. """

        if self.cards.has_key(name):
            self.cardOrder.remove(name)
            del self.cards[name]
        
    def getCardName(self, card):
        """ Extract or create a unique card name. For non-commentary cards, just return the Card's name.
            For commentary cards, create a unique name.
        """
        
        if isinstance(card, Cards.CommentCard) or card.name in ('COMMENT', 'HISTORY'):
            while 1:
                name = "%s-%04d" % (card.name[:3], self.commentIdx)
                self.commentIdx += 1
                if name not in self.cardOrder:
                    break
        else:
            name = card.name
            
        return name
                     
        
    def FITSHeader(self):
        """ Return our cards as a valid FITS file header. """

        header = []
        if 'SIMPLE' not in self.cards:
            header.append(Cards.LogicalCard("SIMPLE", 1).asCard())

        if self.image != None:
            # Use existing required cards if we can.
            #
            if 'BITPIX' not in self.cards:
                header.append(Cards.IntCard("BITPIX", self.depth).asCard())
                header.append(Cards.IntCard("NAXIS", 2).asCard())
                header.append(Cards.IntCard("NAXIS1", self.height).asCard())
                header.append(Cards.IntCard("NAXIS2", self.width).asCard())

        for cardName in self.cardOrder:
            card = self.cards[cardName]
            header.append(card.asCard())
        header.append(Cards.ValuelessCard("END").asCard())

        self.fillHeader(header)
        return ''.join(header)


    def _verify(self):
        """ Look for obvious structural errors. """
        
        if idx == 0:
            if card.name != 'SIMPLE':
                raise RuntimeError("First FITS card is not SIMPLE.")
        if idx == 1:
            if card.name != 'BITPIX':
                raise RuntimeError("Second FITS card is not BITPIX.")
        if idx == 2:
            if card.name != 'NAXIS':
                raise RuntimeError("Third FITS card is not NAXIS.")
        if idx == 3:
            if card.name != 'NAXIS1':
                raise RuntimeError("Fourth FITS card is not NAXIS1.")
        if idx == 4:
            if card.name != 'NAXIS2':
                raise RuntimeError("Fifth FITS card is not NAXIS2.")

    def readFromFile(self, f, lazyData=False):
        """ Create ourselves from an existing FITS header.

        """
        
        # The only card we ignore is END.
        #
        idx = 0
        while 1:
            cardData = f.read(80)
            if len(cardData) != 80:
                raise RuntimeError("Could not completely read the input FITS file: %d %d %s" % (idx, len(cardData), cardData))
            idx += 1
            if cardData[0] == ' ':
                continue
            if cardData[:8] == 'END     ':
                break
            
            card = Cards.PreformattedCard(cardData)
                
            self.addCard(card)
            
        # Skip header padding.
        #
        while idx % 36 != 0:
            padding = f.read(80)
            if len(padding) != 80:
                raise RuntimeError("Could not finish reading the FITS header.")
            idx += 1
            
        # Read data
        #
        here = f.tell()
        f.seek(0, 2)
        end = f.tell()
        f.seek(here, 0)
        
        self.image = f.read(end-here)
        
    def parseCardData(self, rawCard):
        """ Parse an 80-character string as an appropriately typed FITS card.
        """
        
        # Look for easy ones first: commentary cards.
        name = rawCard[:8]
        if name in ('HISTORY ', 'COMMENT', '        '):
            return Cards.CommentCard(rawCard[:8], rawCard[9:])
        
        
        
    def fillHeader(self, header):
        """ Properly fill the header to blocks of 36 cards. """

        cnt = len(header)
        fillCnt = 36 - (cnt % 36)
        if fillCnt != 36:
            for i in range(fillCnt):
                header.append(Cards.ValuelessCard("").asCard())
        return header
        
    def addImage(self, width, height, depth, pixels):
        """ Add image data, along with its geometry. """
        
        self.width = width
        self.height = height
        self.depth = depth
        
        self.image = pixels
        
    def flipSign(self):
        """ Convert our data from signed to unsigned pixels. Does not change BZERO/BSCALE"""
        
        pixel16.uflip(self.image)
        
    def writeToFile(self, file):
        """ Write ourselves to the given file. """

        # Write the FITS header...
        #
        formattedHeader = self.FITSHeader()
        file.seek(0, 0)
        file.write(formattedHeader)
        file.flush()

        # And the image data...
        #
        if self.image:
            # How much do we need to pad the data?
            rawLen = len(self.image)
            extraLen = 2880 - (rawLen % 2880)
            if extraLen == 2880:
                extraLen = 0
            file.write(self.image)
            if extraLen != 0:
                file.write(' ' * extraLen)
            file.flush()

def main():
    import sys
    f = FITS()
    print "1....6...." * 8 + ":"
    c = Cards.StringCard('ABC',
                         "12345678901234567890123456789012345678901234567890123456789012345678")
    f.addCard(c)
    
    c = Cards.StringCard('ABCD',
                         "1234567890123456789012345678901234567890123456789012345678901234567", 'comment')
    f.addCard(c)

    c = Cards.StringCard('ABCDE',
                         "", 'comment')
    f.addCard(c)

    c = Cards.StringCard('ABCDEF',
                         "1234567890123456789", 'comment')
    f.addCard(c)

    c = Cards.StringCard('AB',
                         "123456789012345678901234567890", 'comment')
    f.addCard(c)
    
    c = Cards.IntCard('DEF11111', 42, 'comment')
    f.addCard(c)

    c = Cards.IntCard('DEF11112', sys.maxint, 'comment')
    f.addCard(c)

    c = Cards.IntCard('DEF11113', -sys.maxint)
    f.addCard(c)

    c = Cards.IntCard('DEF11114', -sys.maxint, 'long long long long long long long long omment')
    f.addCard(c)

    c = Cards.IntCard('DEF11115', -sys.maxint, 'long long long long long long long long comment')
    f.addCard(c)

    c = Cards.IntCard('DEF11116', -sys.maxint, 'long long long long long long long long ccomment')
    f.addCard(c)

    c = Cards.IntCard('DEF11117', -sys.maxint, 'long long long long long long long long cccomment')
    f.addCard(c)

    c = Cards.IntCard('DEF11118', -sys.maxint, 'long long long long long long long long ccccomment')
    f.addCard(c)

    c = Cards.RealCard('REAL1', 1.0, 'one')
    f.addCard(c)
    
    c = Cards.RealCard('REAL2', -1.0, 'one')
    f.addCard(c)
    
    c = Cards.RealCard('REAL3', 0.0)
    f.addCard(c)
    
    c = Cards.RealCard('REAL4', -1234.50, 'one')
    f.addCard(c)
    
    c = Cards.RealCard('REAL5', 1e300, 'one')
    f.addCard(c)
    
    c = Cards.LogicalCard('LOG1', 1, 'true-ish')
    f.addCard(c)
    
    c = Cards.LogicalCard('LOG2', 0, 'false-ish')
    f.addCard(c)

    h = f.FITSHeader()

    print ':\n'.join(h)
    print "lines=%d, bytes=%d" % (len(h), len(''.join(h)))
    
    f0 = open("/home/cloomis/build/pyfits/grim_mars.0004.fit", "r")
    inF = FITS(inputFile=f0)
    inF.addCard(c, after='NAXIS2')

    c = Cards.CommentCard('COMMENT', "Ohh, ahh")
    inF.addCard(c)

    c = Cards.CommentCard('COMMENT', "Ohh, ahh 2")
    inF.addCard(c)

    c = Cards.CommentCard('COMMENT', "Ohh, ahh 3")
    inF.addCard(c)

    c = Cards.CommentCard('COMMENT', "Ohh, ahh 4")
    inF.addCard(c)

    c = Cards.CommentCard('COMMENT', "Ohh, ahh 5")
    inF.addCard(c)

    c = Cards.CommentCard('COMMENT', "Ohh, ahh 6")
    inF.addCard(c)

    c = Cards.CommentCard('COMMENT', "Ohh, ahh 6")
    inF.addCard(c)

    c = Cards.CommentCard('COMMENT', "Ohh, ahh 6")
    inF.addCard(c)

    c = Cards.CommentCard('COMMENT', "Ohh, ahh 6")
    inF.addCard(c)

    c = Cards.CommentCard('COMMENT', "Ohh, ahh 6")
    inF.addCard(c)

    c = Cards.CommentCard('COMMENT', "Ohh, ahh X")
    inF.addCard(c)
    c = Cards.CommentCard('COMMENT', "Ohh, ahh Y")
    inF.addCard(c)
    c = Cards.CommentCard('COMMENT', "Ohh, ahh Z")
    inF.addCard(c)

    f1 = open("/home/cloomis/build/pyfits/gzzz.fit", "w+")
    inF.writeToFile(f1)
    
if __name__ == "__main__":
    fin = open('/Users/cloomis/Desktop/zzzz.fits')
    fout = open('/Users/cloomis/Desktop/zout.fits', 'w+')
    
    f = FITS()
    f.readFromFile(fin)
    fin.close()
    
    f.flipSign()
    f.addCard(Cards.RealCard('BSCALE', 1.0), after='NAXIS2')
    f.addCard(Cards.RealCard('BZERO', 32768.0), after='BSCALE')
    
    f.addCard(Cards.CommentCard('COMMENT', "CPL's comment"))
    f.addCard(Cards.StringCard('INSTRUME', "NICFPS"), allowOverwrite=True)
    
    f.writeToFile(fout)
    
    
    
    
