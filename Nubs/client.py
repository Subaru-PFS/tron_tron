import time

from Hub.Command.Decoders.ASCIICmdDecoder import ASCIICmdDecoder
from Hub.Reply.Encoders.PyReplyEncoder import PyReplyEncoder
from Hub.Nub.Commanders import StdinNub
from Hub.Nub.Listeners import SocketListener

import g
import hub

name = 'client'
listenPort = 6094

def acceptStdin(in_f, out_f, addr=None):
    """ Create a command source with the given fds as input and output. """
    
    nubID = g.nubIDs.gimme()

    d = ASCIICmdDecoder(needCID=True, needMID=True, 
                        EOL='\n', name=name,
                        debug=1)
    e = PyReplyEncoder(name=name, debug=1)
    c = StdinNub(g.poller, in_f, out_f,
                 name='%s_%d' % (name, nubID),
                 encoder=e, decoder=d, debug=1)

    c.taster.addToFilter(('tcc', 'dis', 'hub', 'msg'), (), ('hub'))
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
