#!/usr/bin/env python

""" FITS.py - a very simple FITS class group.

    FITS files generated here always have fixed-format cards, but
    free-format cards can be read.
    
"""

import FITSCard

class FITS:
    """ One FITS file contains a ordered list of FITS cards, plus
    optional image data.

    The 
    """

    standardCards = ('SIMPLE', 'BITPIX', 'NAXIS', 'END')

    def __init__(self):
        self.cards = []
        self.cardNames = {}
        self.image = None

    def addCard(self, card, allowOverwrite=0):
        """ Add a single card to the FITS header. Standard headers
        cannot be added. Disallow replacing headers unless
        allowOverwrite is true. """

        if self.cardNames.has_key(card.name) and not allowOverwrite:
            raise KeyError("cannot overwrite existing card for '%s'" % (card.name))
        if card.name in FITS.standardCards:
            # Not checking for NAXISn yet -- CPL
            raise KeyError("cannot define card named '%s'" % (card.name))
            
        self.cards.append(c)
        self.cards.cardNames[c.name] = c

    def asFITS(self):
        """ Return this FITS file as a valid FITS file. """

        header = []
        
        
    def addImage(self, width, height, depth, pixels):
        pass
    
    def output(self):
        pass
    
if __name__ == "__main__":
    c = CharCard('ABC', "012'567890123456789012345678901234567890123456789012345678901234567890", '')
    print c.asCard()
    
