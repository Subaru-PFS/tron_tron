import os

import g
import Hub
import hub

name = 'dcamera'

def start(poller):

    stop()

    initCmds = ('status',)
    # safeCmds = r'status\s*$'
    safeCmds = r'.*'

    d = Hub.ASCIIReplyDecoder(debug=1)
    e = Hub.ASCIICmdEncoder(debug=1, sendCommander=True)
    nub = Hub.SocketActorNub(poller, 'dcamera-icc', 5000,
                             name=name, encoder=e, decoder=d,
                             initCmds=initCmds, safeCmds=safeCmds,
                             needsAuth=False,
                             logDir=os.path.join(g.logDir, name),
                             debug=1)
    hub.addActor(nub)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n

