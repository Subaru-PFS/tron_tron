import Hub
import g
import hub

name = 'extin'
listenPort = 6099

def acceptExtin(in_f, out_f, addr=None):
    """ Create a command source with the given fds as input and output. """
    
    # Force new versions to be loaded.
    #
    # deep_reload(Hub)
    
    nubID = g.nubIDs.gimme()

    d = Hub.ASCIIReplyDecoder(debug=1)
    e = Hub.ASCIICmdEncoder(debug=1, sendCommander=True)
    nub = Hub.StdinNub(poller, in_f, out_f,
                       name=name, encoder=e, decoder=d, debug=1)

    c.taster.addToFilter(('tcc', 'dis', 'hub', 'msg'), (), ('hub'))
    hub.addActor(nub)
    
def start(poller):
    stop()
    
    l = Hub.SocketListener(poller, listenPort, name, acceptExtin)
    hub.addAcceptor(l)
    
def stop():
    l = hub.findAcceptor(name)
    if l:
        hub.dropAcceptor(l)
        del l
