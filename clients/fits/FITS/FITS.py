#!/usr/bin/env python

""" FITS.py - a very simple FITS class group.

"""

import Cards

class FITS:
    """ One FITS file contains a ordered list of FITS cards, plus
    optional image data.

    """

    # Cards that we manage, and that cannot be added by the caller.
    # Ehh, bad idea.
    #
    standardCards = ('SIMPLE', 'BITPIX', 'NAXIS', 'NAXIS1', 'NAXIS2', 'END')

    def __init__(self):
        self.cards = []
        self.cardNames = {}

        self.haveImage = None
        self.image = None

    def addCard(self, card, allowOverwrite=0):
        """ Add a single card to the FITS header. Standard headers
        cannot be added. Disallow replacing headers unless
        allowOverwrite is true. """

        if self.cardNames.has_key(card.name) and not allowOverwrite:
            raise KeyError("cannot overwrite existing card for '%s'" % (card.name))
        if card.name in FITS.standardCards:
            raise KeyError("cannot define card named '%s'" % (card.name))
            
        self.cards.append(card)
        self.cardNames[card.name] = card

    def addRawCards(self, s):
        """ Add a block of data to the FITS header as a list of unchecked cards.

            The only error comes from a block not being 80n bytes long. The
            content of the blockis not examined.
            """

        if len(s) % 80 != 0:
            raise ValueError('addRawCards argument (%d bytes) is not an integral number of FITS cards.')

        # Chop the argument into 1-card pieces and add them.
        #
        
        
            
    def FITSHeader(self):
        """ Return our cards as a valid FITS file header. """

        header = []
        header.append(Cards.LogicalCard("SIMPLE", 1).asCard())

        if self.haveImage:
            header.append(Cards.IntCard("BITPIX", self.depth).asCard())
            header.append(Cards.IntCard("NAXIS", 2).asCard())
            header.append(Cards.IntCard("NAXIS1", self.height).asCard())
            header.append(Cards.IntCard("NAXIS2", self.width).asCard())
            
        for card in self.cards:
            header.append(card.asCard())
        header.append(Cards.ValuelessCard("END").asCard())

        self.fillHeader(header)
        return ''.join(header)

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
        self.haveImage = 1
        
    def writeToFile(self, file):
        """ Write ourselves to the given file. """

        # Write the FITS header...
        #
        formattedHeader = self.FITSHeader()
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

import sys
if __name__ == "__main__":
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
    
