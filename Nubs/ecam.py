import g
import Hub
import hub

name = 'ecam'

def start(poller):

    stop()

    d = Hub.ASCIIReplyDecoder(debug=9)
    e = Hub.ASCIICmdEncoder(debug=9, sendCommander=True)
    nub = Hub.ShellNub(poller, ['/usr/bin/env',
                                'PATH=/usr/local/bin:/usr/bin',
                                'PYTHONPATH=%s/Client:%s' % (g.home, g.home),
                                'clients/guiders/%s.py' % (name)],
                       name=name, encoder=e, decoder=d,
                       debug=9)
    hub.addActor(nub)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n

