from Card import Card

class ValuelessCard(Card):
    """

    """
    
    def __init__(self, name, comment=None):
        Card.__init__(self, name, comment)

    def formatValue(self):

        return None


