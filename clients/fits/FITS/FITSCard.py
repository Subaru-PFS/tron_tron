#!/usr/bin/env python

""" FITS.py - a very simple FITS class group.

    FITS files generated here always have fixed-format cards, but
    free-format cards can be read.
    
"""

class FITSCard:
    """ One FITS card.

    The type would be implicit in the value, but for the existence of
    the FITS boolean type. So we use subclasses instead:

    CharCard, IntCard, FloatCard, CommentCard, BoolCard
    
    We raise exceptions on invalid keyword names and on invalid
    data. I suppose one could truncate or otherwise reformat, but I'd
    rather force a fix by the caller. Comments will be truncated,
    though. 
    
    """

    validNameChars = 'ABCDEFHIJKLMNOPQRSTUVWXYZ0123456789-_'

    def __init__(self, name, comment=None, simple=1):
        
        # Sanity tests
        if type(name) != type(''):
            raise KeyError('card name %s is not a string, but a %s' %
                           (`name`, `type(name)`))
        if len(name) > 8:
            raise KeyError('card name %s is longer than eight characters' %
                           (name,))
        
        for c in name:
            if not c in FITSCard.validNameChars:
                raise KeyError('card name %s contains the invalid character "%s"' %
                               (name, c))

        self.name = name

        # Test later, I'm afraid.
        self.comment = comment

    def asCard(self):
        """ Return this card formatted for a FITS header. """

        if not self.has_key('formatted_card'):
            self.__format()
        
        return self.formatted_card

    def __format(self):
        """ Build the formatted representation of this card.

            There are three pieces to a FITS card: the name, the value, and the comment.
            Both the name and the value 
        """

        if self.has_key('formatted_card'):
            return self.formatted_card
        
        
    def format_comment(self):
        """ Add/trim optional comment. """

        if self.comment == None:
            return
        
        card_len = len(self.formatted_card)
        comment_len = len(self.comment)

        # Try, in order, to format the comment as:
        #  card / comment
        
class CharCard(FITSCard):
    """
    If the value is a fixed format character string, column 11 shall
    contain a single quote (hexadecimal code 27, ``'''); the string
    shall follow, starting in column 12, followed by a closing single
    quote (also hexadecimal code 27) that should not occur before
    column 20 and must occur in or before column 80. The character
    string shall be composed only of ASCII text. A single quote is
    represented within a string as two successive single quotes, e.g.,
    O'HARA = 'O''HARA'. Leading blanks are significant; trailing
    blanks are not.

    Free format character strings follow the same rules as fixed
    format character strings except that the starting and closing
    single quote characters may occur anywhere within columns
    11-80. Any columns preceding the starting quote character and
    after column 10 must contain the space character.

    Note that there is a subtle distinction between the following 3 keywords: 

    KEYWORD1= ''                   / null string keyword
    KEYWORD2= '   '                / blank keyword
    KEYWORD3=                      / undefined keyword

    The value of KEYWORD1 is a null, or zero length string whereas the
    value of the KEYWORD2 is a blank string (nominally a single blank
    character because the first blank in the string is significant,
    but trailing blanks are not). The value of KEYWORD3 is undefined
    and has an indeterminate datatype as well, except in cases where
    the data type of the specified keyword is explicitly defined in
    this standard.

    The maximum allowed length of a keyword string is 68 characters
    (with the opening and closing quote characters in columns 11 and
    80, respectively). In general, no length limit less than 68 is
    implied for character-valued keywords.
    """
    
    def __init__(self, name, value, comment):
        FITSCard.__init__(self, name, comment)

        # Sanity tests
        len = 1
        filtered_value = ''
        for c in value:
            if c < ' ' or c > '~':
                raise ValueError('card value for %s contains the invalid character 0x%02x' %
                                 (name, int(c)))
            if c == "'":
                filtered_value += "''"
                len += 2
            else:
                filtered_value += c
                len += 1
        if len > 68:
            raise ValueError('card value for %s is longer than 68 characters: "%s"' %
                             (name, filtered_value))
        self.value = value
        self.filtered_value = filtered_value
        self.val_length = len + 2

    def formatValue(self):
        pass
    
    def formatAsCard(self):
        
        if self.val_length < 8:
            val = "'%s%s'" % (self.filtered_value, ' ' * (8 -
                                                          self.val_length))
        else:
            val = "'%s'" % (self.filtered_value)
        self.formatted_card = "%-8s= %s" % (self.name, val)
        self.formatComment()

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
    
