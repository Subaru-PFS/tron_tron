import os.path

import g
import Hub
import hub

name = 'gcam'

def start(poller):

    stop()

    d = Hub.ASCIIReplyDecoder(debug=1)
    e = Hub.ASCIICmdEncoder(debug=1, sendCommander=True)
    nub = Hub.ShellNub(poller, ['/usr/bin/env',
                                'PATH=/usr/local/bin:/bin:/usr/bin',
                                'PYTHONPATH=%s/Client:%s' % (g.home, g.home),
                                'clients/guiders/%s.py' % (name)],
                       name=name, encoder=e, decoder=d,
                       logDir=os.path.join(g.logDir, name),
                       debug=1)
    hub.addActor(nub)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n

