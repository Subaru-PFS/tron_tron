__all__ = [ 'ParseException' ]

import exceptions

class ParseException(exceptions.Exception):
    """ A mini Exception used to pass useful information up from the bowels of the parser.

    In particular:
        leftoverText is whatever text has not been parsed.
        KVs is whatever keys have already been parsed.
        
    """
    
    def __init__(self, leftoverText, KVs=None):
        exceptions.Exception.__init__(self)

        self.leftoverText = leftoverText
        self.KVs = KVs

    def __str__(self):
        return "ParseException(leftover=%s, KVs=%s)" % (self.leftoverText, self.KVs)
    
    def prependText(self, t):
        """ Insert t at the beginning of .leftoverText. """

        self.leftoverText = t + self.leftoverText

    def setKVs(self, KVs):
        """ Set .KVs. """

        self.KVs = KVs
        
