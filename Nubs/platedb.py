import os.path

from Hub.Command.Encoders.ASCIICmdEncoder import ASCIICmdEncoder
from Hub.Reply.Decoders.ASCIIReplyDecoder import ASCIIReplyDecoder
from Hub.Nub.SocketActorNub import SocketActorNub
from Hub.Nub.Listeners import SocketListener
import CPL.cfg
import hub
import g

name = 'platedb'

def start(poller):
    cfg = CPL.cfg.get('hub', 'actors', doFlush=True)[name]
    stop()

    initCmds = ('ping',
                'status')
    # safeCmds = r'^\s*info\s*$'

    d = ASCIIReplyDecoder(debug=1)
    e = ASCIICmdEncoder(sendCommander=True, useCID=False, debug=1)
    nub = SocketActorNub(poller, cfg['host'], cfg['port'],
                         name=name, encoder=e, decoder=d,
                         grabCID=True,
                         # initCmds=initCmds, # safeCmds=safeCmds,
                         needsAuth=False,
                         logDir=os.path.join(g.logDir, name),
                         debug=1)
    hub.addActor(nub)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n
