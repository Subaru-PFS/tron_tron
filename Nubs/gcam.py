import os.path

import g
import Hub
import hub

name = 'gcam'

def start(poller):

    stop()

    initCmds = ('status',)
    # safeCmds = r'status\s*$'
    safeCmds = r'.*'

    d = Hub.ASCIIReplyDecoder(debug=1)
    e = Hub.ASCIICmdEncoder(debug=1, sendCommander=True)
    nub = Hub.ShellNub(poller, ['/usr/bin/env',
                                'PATH=/usr/local/bin:/bin:/usr/bin',
                                'PYTHONPATH=%s/Client:%s' % (g.home, g.home),
                                'clients/guiders/%s.py' % (name)],
                       name=name, encoder=e, decoder=d,
                       logDir=os.path.join(g.logDir, name),
                       needsAuth=True,
                       grabCID='ping',
                       # initCmds=initCmds,
                       safeCmds=safeCmds,
                       debug=1)
    hub.addActor(nub)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n

