import Hub
import hub

name = 'expose'

def start(poller):

    stop()

    d = Hub.ASCIIReplyDecoder(debug=1)
    e = Hub.ASCIICmdEncoder(debug=1, sendCommander=True)
    nub = Hub.ShellNub(poller, ['/usr/bin/env',
                                'PYTHONPATH=%s/Client:%s' % (hub.home, hub.home),
                                'clients/%s/%s.py' % (name, name)],
                       name=name, encoder=e, decoder=d, debug=1)
    hub.addActor(nub)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n

