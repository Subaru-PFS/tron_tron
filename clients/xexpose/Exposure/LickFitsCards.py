import mmap
import os

class LickFitsCards(object):
    """ LickFitsCards -- efficiently copy a new set of FITS cards into a FITS PHDU which
                         has some extra 'dummy' cards.

    The PHDU for the FITS file must have a sequence of one or more cards of the form JUNK%d,
    where JUNK is a prefixpassed in to our constructor.
    """
    
    CARDLEN = 80
    ENDCARD = "%-80s" % ("END")
    FILLERCARD = "%-80s" % ("COMMENT")
    
    def __init__(self, filename, dummyPrefix, cmd=None):
        """ LickFitsCards(filename, dummyPrefix) -
                   open FITS file $filename in order to swap $dummyPrefix-cards with
                   other cards..
        """
        self.cmd = cmd
        if self.cmd:
            self.cmd.warn('debug="Licking %s with prefix=%s"' % (filename, dummyPrefix))
            
        self.dummyPrefix = dummyPrefix.upper()
        self.freeCardIdx = 0
        
        self.fd = None
        self.mmap = None
        self._setup(filename)
        
    def __del__(self):
        if self.fd != None:
            self.close()

    def _nextFreeCardName(self):
        return "%s%d" % (self.dummyPrefix, self.freeCardIdx)

    def _seekFirstFreeCard(self):
        """ Move the file pointer to the start of the first dummy card. """
        cardName = self._nextFreeCardName()
        while True:
            cardStart = self.mmap.tell()
            card = self.mmap.read(self.CARDLEN)
            if not card or card == self.ENDCARD:
                raise RuntimeError("no cards match %s" % (cardName))
            if card.startswith(cardName):
                self.mmap.seek(cardStart)        # Move back to the start of this card.
                return

    def _setup(self, filename):
        """ open the given file, and move to the start of the 1st dummy card. """

        self.filename = filename
        self.fd = os.open(filename, os.O_RDWR)
        # The python docs say that mmap(len=0) maps the whole file. But POSIX doesn't,
        # so we do it by hand.
        self.mmap = mmap.mmap(self.fd,os.stat(filename).st_size,
                              mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE)
        self._seekFirstFreeCard()

    def _neaten(self):
        """ replace any unconsumed dummy cards with COMMENTs.

        Note: this could be more clever: move the cards to the end of the header, etc.
        """
        try:
            self.swapCards([self.FILLERCARD] * 100)
        except:
            pass
        
    def close(self):
        self._neaten()
        self.mmap.close()
        self.mmap = None
        os.close(self.fd)
        self.fd = None
        
    def swapCards(self, newCards):
        """ replace dummy cards with newCards. We must be
            on a dummy card on entry.

            Args:
                newCards   - one 80-byte string, or a list/array of same.
                
            Raises:
                RuntimeError if the current position is not on a dummy card,
                             or if we run out of dummy cards.
        """

        if self.cmd:
            import CPL
            self.cmd.warn('debug=%s' % (CPL.qstr('swapping in %s') % (newCards)))
            
        if type(newCards) == str:
            newCards = [newCards]

        for newCard in newCards:
            assert(len(newCard) == 80)
        
            cardName = self._nextFreeCardName()
            start = self.mmap.tell()
            card = self.mmap.read(self.CARDLEN)
            if not card.startswith(cardName):
                raise RuntimeError("no more dummy cards available: %d consumed" \
                                   % (self.freeCardIdx))

            # Go back and replace the card:
            self.mmap.seek(start)
            self.mmap.write(newCard)
            self.freeCardIdx += 1
        
