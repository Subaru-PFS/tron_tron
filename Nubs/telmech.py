#!/usr/bin/env python

import os.path

import g
import Hub
import hub

name = 'telmech'

def start(poller):

    stop()
    initCmds = ['status']
    safeCmds = r'.*status'

    d = Hub.ASCIIReplyDecoder(debug=1)
    e = Hub.ASCIICmdEncoder(debug=1, sendCommander=True)
    nub = Hub.ShellNub(poller, ['/usr/bin/env',
                                'PATH=/usr/local/bin:/usr/bin',
                                'PYTHONPATH=%s/Client:%s' % (g.home, g.home),
                                'clients/%s/%s.py' % (name, name)],
                       name=name, encoder=e, decoder=d,
                       needsAuth=True,
                       grabCID=True,
                       initCmds=initCmds, safeCmds=safeCmds,
                       logDir=os.path.join(g.logDir, name),
                       debug=1)
    hub.addActor(nub)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n

