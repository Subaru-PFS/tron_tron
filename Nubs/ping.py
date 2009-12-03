import os.path

import g
import hub

from Hub.Command.Encoders.ASCIICmdEncoder import ASCIICmdEncoder
from Hub.Reply.Decoders.ASCIIReplyDecoder import ASCIIReplyDecoder
from Hub.Nub.ShellNub import ShellNub

name = 'ping'

def start(poller):

    stop()

    d = ASCIIReplyDecoder(debug=1)
    e = ASCIICmdEncoder(debug=1, sendCommander=True)
    nub = ShellNub(poller, ['/usr/bin/env',
#                            'PATH=/usr/local/bin:/usr/bin',
                            'clients/%s/%s.py' % (name, name)],
                   name=name, encoder=e, decoder=d,
                   #logDir=os.path.join(g.logDir, name),
                   debug=1)
    hub.addActor(nub)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n

