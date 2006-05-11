import os.path

import Hub
import hub
import g

name = 'apollo'

def start(poller):
    # deep_reload(Hub)
    
    stop()

    initCmds = ('ping',)
    safeCmds = r'^\s*status\s*$'

    d = Hub.ASCIIReplyDecoder(EOL='\n', CIDfirst=True, debug=1)
    e = Hub.ASCIICmdEncoder(EOL='\n', debug=1)
    dis = Hub.SocketActorNub(poller, 'cocoa', 9879,
                             name=name, encoder=e, decoder=d,
                             needsAuth=True,
                             grabCID='ping',
                             logDir=os.path.join(g.logDir, name),
                             debug=1)
    hub.addActor(dis)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n
