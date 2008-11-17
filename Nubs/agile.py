import os.path

import Hub
import hub
import g

name = 'agile'

def start(poller):
    # deep_reload(Hub)
    
    stop()

    initCmds = ('status',)
    safeCmds = r'^\s*status\s*$'

    d = Hub.ASCIIReplyDecoder(EOL='\r\n', CIDfirst=True, debug=1)
    e = Hub.ASCIICmdEncoder(EOL='\n', debug=1)
    dis = Hub.SocketActorNub(poller, 'nimble', 1025,
                             name=name, encoder=e, decoder=d,
                             grabCID='ping', # Send to get a CID.
                             initCmds=initCmds, safeCmds=safeCmds,
                             needsAuth=True,
                             logDir=os.path.join(g.logDir, name),
                             debug=1)
    hub.addActor(dis)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n
