import g
import Hub
import hub

name = 'grimExpose'

def start(poller):

    stop()

    d = Hub.ASCIIReplyDecoder(debug=1)
    e = Hub.ASCIICmdEncoder(debug=1, sendCommander=True)
    nub = Hub.ShellNub(poller, ['/usr/bin/env',
                                'PYTHONPATH=%s/Client:%s' % (g.home, g.home),
                                'clients/expose/%s.py' % (name)],
                       name=name, encoder=e, decoder=d,
                       needsAuth='grim',
                       debug=1)
    hub.addActor(nub)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n

