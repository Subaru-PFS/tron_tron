import time

import Hub.Command.Decoders as hubDecoders
import Hub.Reply.Encoders as hubEncoders
import Hub.Nub.Commanders as hubCommanders 
from Hub.Nub.Listeners import SocketListener

import g
import hub

name = 'client'
listenPort = 6093
listenHost = 'tron'

def acceptStdin(in_f, out_f, addr=None):
    """ Create a command source with the given fds as input and output. """
    
    nubID = g.nubIDs.gimme()

    d = hubDecoders.ASCIICmdDecoder(needCID=True, needMID=True, 
                                    EOL='\n', hackEOL=True, name=name,
                                    debug=1)
    e = hubEncoders.ASCIIReplyEncoder(EOL='\n', simple=True, debug=1, CIDfirst=True)
    c = hubCommanders.StdinNub(g.poller, in_f, out_f,
                               name='%s.v%d' % (name, nubID),
                               encoder=e, decoder=d, debug=1)

    # By default, listen to nothing but replies to our commands and messages from the hub.
    c.taster.addToFilter(('hub',), (), ('hub',))
    hub.addCommander(c)

def start(poller):
    stop()
    
    l = SocketListener(poller, listenPort, name, acceptStdin, host=listenHost)
    hub.addAcceptor(l)
    
    time.sleep(1)

def stop():
    l = hub.findAcceptor(name)
    if l:
        hub.dropAcceptor(l)
        del l
