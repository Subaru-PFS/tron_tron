from Card import Card

class CommentCard(Card):
    """
    
5.4.2.4 Commentary Keywords
 
COMMENT Keyword
This  keyword shall have no associated value ; columns 9-80 may contain any ASCII  text. 
Any number of COMMENT card images may appear in a header.

HISTORY Keyword
This keyword shall have no associated value ; columns 9-80 may contain any ASCII  text. 
The text should contain a history of steps and procedures associated with the processing of the associated data.
Any number of HISTORY card images may appear in a header.

Keyword Field is Blank
Columns 1-8 contain ASCII blanks. Columns 9-80 may contain any ASCII  text. 
Any number of card images with blank keyword fields may appear in a header.

    """

    
    def __init__(self, name, value):
        if name not in ('COMMENT', 'HISTORY', '', ' ', '       ', '        '):
            raise ValueError("Invalid FITS comment card name")
        
        Card.__init__(self, name, None)

        self.value = value[:80-9+1]
        
    
    def formatValue(self):
        return "%-72s" % self.value
    
    def _format(self):
        """ Build the formatted representation of this card.

            There are three pieces to a FITS card: the name, the value, and the comment.
        """
        name = self.formatName()
        val = self.formatValue()

        
        self.formatted_card = "%s%s" % (name, val)
        


