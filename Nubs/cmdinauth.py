import Hub
import g
import hub

name = 'cmdinauth'
listenPort = 9880

def acceptStdin(in_f, out_f, addr=None):
    """ Create a command source with the given fds as input and output. """
    
    # Force new versions to be loaded.
    #
    # deep_reload(Hub)
    
    nubID = g.nubIDs.gimme()

    otherIP, otherPort = in_f.getpeername()
    try:
        otherFQDN = socket.getfqdn(otherIP)
    except:
        otherFQDN = "unknown"
        
    d = Hub.ASCIICmdDecoder(needCID=False, 
                            EOL='\n', name=name, debug=1)
    e = Hub.ASCIIReplyEncoder(name=name, simple=True, debug=1, needCID=False)
    c = Hub.AuthStdinNub(g.poller, in_f, out_f,
                         name='%s-%d' % (name, nubID),
                         encoder=e, decoder=d, debug=1,
                         type='cmdin', isUser=True, needsAuth=True,
                         otherIP=otherIP, otherFQDN=otherFQDN)

    hub.addCommander(c)
    
def start(poller):
    stop()
    
    l = Hub.SocketListener(poller, listenPort, name, acceptStdin)
    hub.addAcceptor(l)
    
def stop():
    l = hub.findAcceptor(name)
    if l:
        hub.dropAcceptor(l)
        del l
