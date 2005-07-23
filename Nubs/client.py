import time

import Hub
import g
import hub

name = 'client'
listenPort = 6094

def acceptStdin(in_f, out_f, addr=None):
    """ Create a command source with the given fds as input and output. """
    
    # Force new versions to be loaded.
    #
    reload(Hub)
    
    nubID = g.nubIDs.gimme()

    d = Hub.ASCIICmdDecoder(needCID=True, needMID=True, 
                            EOL='\n', name=name,
                            debug=1)
    e = Hub.PyReplyEncoder(name=name, debug=1)
    c = Hub.StdinNub(g.poller, in_f, out_f,
                     name='%s-%d' % (name, nubID),
                     encoder=e, decoder=d, debug=1)
    # , forceUser='APO.%s' % (nubID),

    c.taster.addToFilter(('tcc', 'dis', 'hub', 'msg'), (), ('hub'))
    hub.addCommander(c)

    time.sleep(1)

    
def start(poller):
    stop()
    
    l = Hub.SocketListener(poller, listenPort, name, acceptStdin)
    hub.addAcceptor(l)
    
    time.sleep(1)

def stop():
    l = hub.findAcceptor(name)
    if l:
        hub.dropAcceptor(l)
        del l
