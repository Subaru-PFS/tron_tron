import os
import time

from Hub.Command.Decoders.ASCIICmdDecoder import ASCIICmdDecoder
from Hub.Reply.Encoders.ASCIIReplyEncoder import ASCIIReplyEncoder
from Hub.Nub.Commanders import StdinNub
from Hub.Nub.Listeners import SocketListener

import g
import hub

name = 'nclient'
listenPort = 6095

def acceptStdin(in_f, out_f, addr=None):
    """ Create a command source with the given fds as input and output. """
    
    all = ('*',)

    nubID = g.nubIDs.gimme()
    fullname = '%s_%d' % (name, nubID)
    
    d = ASCIICmdDecoder(needCID=True, needMID=True, 
                        EOL='\n', hackEOL=True,
                        name=name, debug=2)
    e = ASCIIReplyEncoder(CIDfirst=True, name=name, debug=2)
    c = StdinNub(g.poller, in_f, out_f,
                 name=fullname,
                 logDir=os.path.join(g.logDir, fullname),
                 encoder=e, decoder=d, debug=2)

    c.taster.addToFilter(all, (), all)
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
