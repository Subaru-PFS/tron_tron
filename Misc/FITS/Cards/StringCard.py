from Card import Card

class StringCard(Card):
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
    
    def __init__(self, name, value, comment=None):
        Card.__init__(self, name, comment)

        if type(value) != type(''):
            raise 'hell', 'card value for %s is not a string, but a %s' % (name, type(value))

        # Build a sanity-checked formatted string. Escape quotes.
        #
        len = 0
        filtered_value = ''
        for c in value:
            if c < ' ' or c > '~':
                #raise 'hell', 'card value for %s contains the invalid character 0x%02x' \
                #      % (name, int(c))
                filtered_value += '?'
                len += 1
            elif c == "'":
                filtered_value += "''"
                len += 2
            else:
                filtered_value += c
                len += 1
        if len > 68:
            filtered_value = filtered_value[:68]
            #raise 'hell', 'card value for %s is longer than 68 characters: "%s"' \
            #      % (name, filtered_value)
        self.value = value              # Keep original value around for posterity.
        self.filtered_value = filtered_value

        self.val_length = len + 2
        
    def formatValue(self, fixed_format=0):
        """ Return the string as a fixed or free format FITS card string. """

        if fixed_format and self.val_length < 8:
            val = "'%s%s'" % (self.filtered_value,
                              ' ' * (8 - self.val_length))
        else:
            val = "'%s'" % (self.filtered_value)

        return val

