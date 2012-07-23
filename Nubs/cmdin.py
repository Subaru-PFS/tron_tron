from Hub.Command.Decoders.ASCIICmdDecoder import ASCIICmdDecoder
from Hub.Reply.Encoders.ASCIIReplyEncoder import ASCIIReplyEncoder
from Hub.Nub.Commanders import StdinNub
from Hub.Nub.Listeners import SocketListener

import g
import hub

name = 'cmdin'
listenPort = 6098

def acceptStdin(in_f, out_f, addr=None):
    """ Create a command source with the given fds as input and output. """
    
    nubID = g.nubIDs.gimme()

    d = ASCIICmdDecoder(needCID=False, 
                        EOL='\r\n', name=name, debug=5)
    e = ASCIIReplyEncoder(name=name, simple=True, debug=5)
    c = StdinNub(g.poller, in_f, out_f,
                 name='%s.v%d' % (name, nubID),
                 encoder=e, decoder=d, debug=5)
    # c.taster.addToFilter(('*'), (), ('*'))
    hub.addCommander(c)
    
def start(poller):
    stop()
    
    l = SocketListener(poller, listenPort, name, acceptStdin)
    hub.addAcceptor(l)
    
def stop():
    l = hub.findAcceptor(name)
    if l:
        hub.dropAcceptor(l)
        del l
