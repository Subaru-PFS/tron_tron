import socket
import time

import Hub
import g
import hub
import os

name = 'TUI'
listenPort = 9877

def acceptTUI(in_f, out_f, addr=None):
    """ Create a command source with the given fds as input and output. """
    
    # Fetch a unique ID
    #
    nubID = g.nubIDs.gimme()

    # This is gross, gross, gross. Basically, I want to stop the apollo
    # traffic until it is requested. So I need to add a taster filtering call which
    # specifies that, instead of enumerating all the acceptable ones. Ugh.
    all = ('tcc','mcp',
           'hub','msg')
    all = ('*',)
    
    allXX = ('dcam', 'ecam', 'gcam', 'tcam',
             'dcamera', 'ecamera', 'gcamera', 'tcamera',
             'disExpose', 'echelleExpose', 'nicfpsExpose',
             'spicamExpose', 'tspecExpose',
             'nicfps', 'dis', 'echelle','spicam', 'tspec',
             'tcc', 'tlamps', 'hub', 'msg',
             'perms', 'auth', 'fits',
             'cm', 'nfocus', 'telmech', 'gmech',
             'agile','agileExpose')
    
    otherIP, otherPort = in_f.getpeername()
    try:
        otherFQDN = socket.getfqdn(otherIP)
    except:
        otherFQDN = "unknown"

    # os.system("/usr/bin/sudo /usr/local/bin/www-access add %s" % (otherIP))
        
    d = Hub.ASCIICmdDecoder(needCID=False, EOL='\r\n', debug=1)
    e = Hub.ASCIIReplyEncoder(EOL='\r', simple=True, debug=1, CIDfirst=True)
    c = Hub.AuthStdinNub(g.poller, in_f, out_f,
                         name='%s-%d' % (name, nubID), 
                         encoder=e, decoder=d, debug=1,
                         type='TUI', needsAuth=True,
                         isUser=True,
                         otherIP=otherIP, otherFQDN=otherFQDN)
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
        
