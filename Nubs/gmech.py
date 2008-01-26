import os.path

import Hub
import hub
import g

name = 'gmech'

def start(poller):
    # deep_reload(Hub)
    
    stop()

    initCmds = ()
    safeCmds = r'^\s*status\s*$'

    d = Hub.ASCIIReplyDecoder(EOL='\r\n', CIDfirst=True, debug=1)
    e = Hub.ASCIICmdEncoder(EOL='\n', debug=1)
    gmech = Hub.SocketActorNub(poller, 'localhost', 9879,
                             name=name, encoder=e, decoder=d,
                             needsAuth=True,
                             grabCID='status',
                             logDir=os.path.join(g.logDir, name),
                             debug=1)
    hub.addActor(gmech)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n
