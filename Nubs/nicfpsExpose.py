import os

import g
import Hub
import hub

name = 'nicfpsExpose'

def start(poller):

    stop()

    initCmds = ('getPath',)
    safeCmds = r'getPath'

    d = Hub.ASCIIReplyDecoder(debug=1)
    e = Hub.ASCIICmdEncoder(debug=1, sendCommander=True)
    nub = Hub.ShellNub(poller, ['/usr/bin/env',
                                'PYTHONPATH=%s/Client:%s' % (g.home, g.home),
                                'clients/expose/%s.py' % (name)],
                       name=name, encoder=e, decoder=d,
                       initCmds=initCmds, safeCmds=safeCmds,
                       needsAuth='nicfps',
                       logDir=os.path.join(g.logDir, name),
                       debug=1)
    hub.addActor(nub)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n

