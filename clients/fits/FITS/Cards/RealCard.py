import math

from Card import Card

class RealCard(Card):
    """

    If the value is a fixed format real floating point number, the
    ASCII representation shall appear, right justified, in columns
    11-30.

    A floating point number is represented by a decimal number
    followed by an optional exponent, with no embedded spaces. A
    decimal number consists of a `+' (hexadecimal 2B) or `-'
    (hexadecimal 2D) sign, followed by a sequence of ASCII digits
    containing a single decimal point (`.'), representing an integer
    part and a fractional part of the floating point number. The
    leading `+' sign is optional. At least one of the integer part or
    fractional part must be present. If the fractional part is
    present, the decimal point must also be present. If only the
    integer part is present, the decimal point may be omitted. The
    exponent, if present, consists of an exponent letter followed by
    an integer. Letters in the exponential form (`E' or `D') shall be
    upper case. Note: The full precision of 64-bit values cannot be
    expressed over the whole range of values using the fixed format.

    A free format floating point value follows the same rules as fixed
    format floating point values except that it may occur anywhere
    within columns 11-80.

    [ Craig wonders how one distinguishes between an Integer card and
    a Real card where only the integer part is displayed. ]

    Problems: the standard C library provides no way to specify the
    number of digits to use for the exponent. So we look, and set the
    formatting width accordingly.

    """
    
    def __init__(self, name, value, comment=None, places=None):
        Card.__init__(self, name, comment)

        if type(value) != type(1.0):
            raise 'hell', 'card value for %s is not a real, but a %s' % (name, type(value))

        self.value = value
        self.places = places
        
    def formatValue(self, fixed_format=1):
        """ Return the float as a fixed (default) or free format FITS card string. """

        mantissa, exponent = math.frexp(self.value)
        if fixed_format:
            if (exponent >= 100):
                val = "%+.12E" % (self.value,)
            else:
                val = "%+.13E" % (self.value,)
        else:
            val = "%E" % (self.value,)

        return val


