import Hub
import hub

name = 'cm'

def start(poller):

    stop()

    d = Hub.ASCIIReplyDecoder(debug=9)
    e = Hub.ASCIICmdEncoder(debug=9, sendCommander=True)
    nub = Hub.ShellNub(poller, ['/usr/bin/env',
                                'PYTHONPATH=%s/Client:%s' % (hub.home, hub.home),
                                'clients/cm/cm.py'],
                       name=name, encoder=e, decoder=d,
                       debug=9)
    hub.addActor(nub)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n

