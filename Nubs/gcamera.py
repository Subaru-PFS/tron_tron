import os.path

from Hub.Command.Encoders.ASCIICmdEncoder import ASCIICmdEncoder
from Hub.Reply.Decoders.ASCIIReplyDecoder import ASCIIReplyDecoder
from Hub.Nub.SocketActorNub import SocketActorNub
from Hub.Nub.Listeners import SocketListener
import hub
import g

name = 'gcamera'

def start(poller):
    stop()

    initCmds = ('ping',
                'version',
                'status')

    # safeCmds = r'^\s*info\s*$'

    d = ASCIIReplyDecoder(debug=1)
    e = ASCIICmdEncoder(sendCommander=True, useCID=False, debug=1)
    nub = SocketActorNub(poller, 'hub25m-p.apo.nmsu.edu', 9993,
                         name=name, encoder=e, decoder=d,
                         grabCID=True, # the actor spontaneously generates a line we can eat.
                         initCmds=initCmds, # safeCmds=safeCmds,
                         needsAuth=False,
                         logDir=os.path.join(g.logDir, name),
                         debug=1)
    hub.addActor(nub)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n
