
class Card:
    """ One FITS card.

    The type would be implicit in the value, but for the existence of
    the FITS boolean type. So we use subclasses instead:

    CharCard, IntCard, FloatCard, CommentCard, BoolCard
    
    We raise exceptions on invalid keyword names and on invalid
    data. I suppose one could truncate or otherwise reformat, but I'd
    rather force a fix by the caller. Comments will by default be
    silently truncated, though.
    
    """

    validNameChars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'

    def __init__(self, name, comment=None):
        
        # Sanity tests
        if type(name) != type(''):
            raise 'hell', 'card name %s is not a string, but a %s' \
                  % (`name`, `type(name)`)
        if len(name) > 8:
            raise 'hell', 'card name %s is longer than eight characters' \
                  % (name)
        
        for c in name:
            if not c in Card.validNameChars:
                raise 'hell', 'card bname %s contains the invalid character "%s"' \
                      % (name, c)

        self.name = name

        # Test later, I'm afraid.
        self.comment = comment
        self.debug = 0
        
    def asCard(self):
        """ Return this card formatted for a FITS header. """

        if not hasattr(self, 'formatted_card'):
            self._format()
        # assert(len(self.formatted_card) == 80)
        
        return self.formatted_card

    def _format(self):
        """ Build the formatted representation of this card.

            There are three pieces to a FITS card: the name, the value, and the comment.
        """
        name = self.formatName()
        val = self.formatValue()

        l = len(name) + len("  ")
        if val == None:
            indicator = "  "
            val = ""
        else:
            l += len(val)
            indicator = "= "

        comment = self.formatComment(80-l)
        
        # Finally, put the four pieces together
        #
        self.formatted_card = "%s%s%s%s" % (name, indicator, val, comment)


    def formatName(self):
        """ """

        return "%-8s" % (self.name)


    def formatValue(self):
        raise 'hell', 'Card.formatValue() must be defined by the subclass.'
    
    def formatComment(self, lenAvail):
        """ Add/trim optional comment into a field."""

        if self.comment == None or self.comment.strip() == '':
            return " " * lenAvail
        
        # Try, in order, to format the comment as:
        #  card       / comment, where the / is lined up at column 32
        #  card / comment, skooch the / left
        #  card /comment
        #  card/comment
        #
        comment = self.comment
        commentLen = len(self.comment)

        if commentLen + 3 <= lenAvail:
            comment = "/ %s" % (comment,)
            commentLen += 2
            
            # If possible without truncating the comment, align the '/' on column 32.
            #
            if lenAvail <= 80 - 32:
                leftPad = 0
                rightPad = lenAvail - commentLen
            elif commentLen > 80 - 32:
                leftPad = lenAvail - commentLen
                rightPad = 0
            else:
                leftPad = lenAvail - (80 - 32) - 1
                rightPad = (80 - 32) - commentLen + 1

            ret = "%s%s%s" % (" " * leftPad, comment, " " * rightPad)
        elif commentLen + 2 == lenAvail:
            ret = " /%s" % (self.comment,)
        elif lenAvail >= 1:
            ret = "/%s" % (self.comment[:lenAvail-1])
        else:    
            ret = ""

        if self.debug:
            print "Card : %s" % (locals())
        return ret
        
if __name__ == "__main__":

    from StringCard import StringCard
    from IntCard import IntCard
    from CommentCard import CommentCard
    from PreformattedCard import PreformattedCard
    
    v = "1234567890" * 8

    print v
    for l in range(0, 82):
        c = StringCard('NAME', v[:l], 'T')
#        c.debug=1
        print "%s:" % (c.asCard())

    print v
    for l in range(0, 72):
        c = IntCard('NAME', 1, 'T' * l)
#        c.debug=1
        print "%s:" % (c.asCard())

    print v
    for l in range(0, 82):
        c = StringCard('NAME', v[:l], 'COMMENT'*8)
#        c.debug=1
        print "%s:" % (c.asCard())

    for l in range(0, 82):
        c = CommentCard('HISTORY', 'x'*l)
#        c.debug=1
        print "%s:" % (c.asCard())

    print v
    c = PreformattedCard('TEST    = 1234567890123456789012345678901234567890123456789012345678901234567890')
    print "%s:" % (c.asCard())
    c = PreformattedCard('        901234567890123456789012345678901234567890123456789012345678901234567890')
    print "%s:" % (c.asCard())
    
    
