import os.path

import Hub
import hub
import g

name = 'nicfps'

def start(poller):
    stop()

    initCmds = ('filters status',
                'temp status',
                'pressure status')

    safeCmds = r'status\s*$'

    d = Hub.ASCIIReplyDecoder(EOL='\n', debug=5)
    e = Hub.ASCIICmdEncoder(EOL='\n', debug=5)
    nicfps = Hub.SocketActorNub(poller, 'nicfps', 9878,
                                name=name, encoder=e, decoder=d,
                                initCmds=initCmds, safeCmds=safeCmds,
                                needsAuth=True,
                                logDir=os.path.join(g.logDir, name),
                                debug=5)
    hub.addActor(nicfps)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n
