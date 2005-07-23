import time

import Hub
import g
import hub

name = 'TUI'
listenPort = 9877

def acceptTUI(in_f, out_f, addr=None):
    """ Create a command source with the given fds as input and output. """
    
    # Fetch a unique ID
    #
    nubID = g.nubIDs.gimme()

    all = ('dcam', 'ecam', 'gcam',
           'dcamera', 'ecamera', 'gcamera',
           'disExpose', 'echelleExpose', 'nicfpsExpose',
           'nicfps', 'dis', 'echelle',
           'tcc', 'tlamps', 'hub', 'msg',
           'perms', 'auth', 'fits')
    
    d = Hub.ASCIICmdDecoder(needCID=False, EOL='\r\n', debug=1)
    e = Hub.ASCIIReplyEncoder(EOL='\r', simple=True, debug=1, CIDfirst=True)
    c = Hub.AuthStdinNub(g.poller, in_f, out_f,
                         name='%s-%d' % (name, nubID), 
                         encoder=e, decoder=d, debug=1,
                         type='TUI', needsAuth=True,
                         isUser=True)
    c.taster.addToFilter(all, (), all)
    hub.addCommander(c)

def start(poller):
    reload(Hub)

    stop()

    lt = Hub.SocketListener(poller, listenPort, name, acceptTUI)
    hub.addAcceptor(lt)

def stop():
    a = hub.findAcceptor(name)
    if a:
        hub.dropAcceptor(a)
        del a
        time.sleep(0.5)                 # OK, why did I put this in here?
        
