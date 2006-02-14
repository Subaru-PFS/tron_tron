import os.path

import Hub
import hub
import g

name = 'echelle'

def start(poller):
    stop()

    initCmds = ('status',)
    safeCmds = r'^\s*status\s*$'

    d = Hub.ASCIIReplyDecoder(EOL='\n', CIDfirst=True, debug=1)
    e = Hub.ASCIICmdEncoder(EOL='\n', debug=1)
    dis = Hub.SocketActorNub(poller, 'echelle-icc', 9878,
                             name=name, encoder=e, decoder=d,
                             grabCID='', # Send an empty command just to get a CID.
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
