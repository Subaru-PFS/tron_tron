from Card import Card

class PreformattedCard(Card):
    """ A FITS card that was formatted externally. We get an 80-charatcer string.

    """
    
    def __init__(self, content):

        if len(content) != 80:
            raise 'hell', "PreformattedCard(%r) length (%d) != 80" % (len(content), content)

        name = content[:8]
        Card.__init__(self, name)

        self.formatted_card = content
        


