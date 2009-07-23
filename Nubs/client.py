import time

from Hub.Command.Decoders.ASCIICmdDecoder import ASCIICmdDecoder
from Hub.Reply.Encoders.ASCIIReplyEncoder import ASCIIReplyEncoder
from Hub.Nub.Commanders import StdinNub
from Hub.Nub.Listeners import SocketListener

import g
import hub

name = 'client'
listenPort = 6093

def acceptStdin(in_f, out_f, addr=None):
    """ Create a command source with the given fds as input and output. """
    
    nubID = g.nubIDs.gimme()

    d = ASCIICmdDecoder(needCID=True, needMID=True, 
                        EOL='\n', hackEOL=True, name=name,
                        debug=3)
    e = ASCIIReplyEncoder(EOL='\n', simple=True, debug=1, CIDfirst=True)
    c = StdinNub(g.poller, in_f, out_f,
                 name='%s.v%d' % (name, nubID),
                 encoder=e, decoder=d, debug=1)

    c.taster.addToFilter(('*'), (), ('hub'))
    hub.addCommander(c)

    time.sleep(1)
    
def start(poller):
    stop()
    
    l = SocketListener(poller, listenPort, name, acceptStdin)
    hub.addAcceptor(l)
    
    time.sleep(1)

def stop():
    l = hub.findAcceptor(name)
    if l:
        hub.dropAcceptor(l)
        del l
