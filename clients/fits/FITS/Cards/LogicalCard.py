from Card import Card

class LogicalCard(Card):
    """

    If the value is a fixed format logical constant, it shall appear
    as a T or F in column 30. A logical value is represented in free
    format by a single character consisting of T or F. This character
    must be the first non-blank character in columns 11-80. The only
    characters that may follow this single character are spaces, or a
    slash followed by an optional comment.

    """

    
    def __init__(self, name, value, comment=None):
        Card.__init__(self, name, comment)

        if value:
            self.value = 'T'
        else:
            self.value = 'F'
        
    def formatValue(self, fixed_format=1):
        """ Return the integer as a fixed or free format FITS card string. """

        if fixed_format:
            val = "%20s" % (self.value,)
        else:
            val = "%s" % (self.value,)

        return val


