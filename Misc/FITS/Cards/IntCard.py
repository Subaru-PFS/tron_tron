from Card import Card

class IntCard(Card):
    """

    If the value is a fixed format integer, the ASCII representation
    shall be right justified in columns 11-30. An integer consists of
    a `+' (hexadecimal 2B) or `-' (hexadecimal 2D) sign, followed by
    one or more ASCII digits (hexadecimal 30 to 39), with no embedded
    spaces. The leading `+' sign is optional. Leading zeros are
    permitted, but are not significant. The integer representation
    described here is always interpreted as a signed, decimal number.

    A free format integer value follows the same rules as fixed format
    integers except that it may occur anywhere within columns 11-80.

    """
    
    def __init__(self, name, value, comment=None):
        Card.__init__(self, name, comment)

        if type(value) != type(1):
            raise 'hell', 'card value for %s is not an integer, but a %s' % (name, type(value))
        
        self.value = value
        
    def formatValue(self, fixed_format=1):
        """ Return the integer as a fixed or free format FITS card string. """

        if fixed_format:
            val = "%20d" % (self.value,)
        else:
            val = "%d" % (self.value,)

        return val


