import os.path

import g
import Hub
import hub

name = 'telmech'

def start(poller):

    stop()

    d = Hub.ASCIIReplyDecoder(debug=0)
    e = Hub.ASCIICmdEncoder(debug=0, sendCommander=True)
    nub = Hub.ShellNub(poller, ['/usr/bin/env',
                                'PATH=/usr/local/bin:/usr/bin',
                                'PYTHONPATH=%s/Client:%s' % (g.home, g.home),
                                'clients/%s/%s.py' % (name, name)],
                       name=name, encoder=e, decoder=d,
                       needsAuth=True,
                       logDir=os.path.join(g.logDir, name),
                       debug=0)
    hub.addActor(nub)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n

