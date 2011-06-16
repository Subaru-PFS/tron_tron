import os

from Hub.Command.Encoders.ASCIICmdEncoder import ASCIICmdEncoder
from Hub.Reply.Decoders.ASCIIReplyDecoder import ASCIIReplyDecoder
from Hub.Nub.SocketActorNub import SocketActorNub
from Hub.Nub.Listeners import SocketListener
import CPL.cfg
import hub
import g

# this point to the APOGEE calibration box Java actor 
# running on APOGEE-ICS
name = 'apogeecal'

def start(poller):
    cfg = CPL.cfg.get('hub', 'actors', doFlush=True)[name]
    stop()

    initCmds = ('ping',
                'status')
	
    # safeCmds = r'^\s*info\s*$'
	
    d = ASCIIReplyDecoder(debug=3)
    e = ASCIICmdEncoder(sendCommander=True, useCID=False, debug=3)
    #nub = SocketActorNub(poller, 'hub25m-p.apo.nmsu.edu', 18281,
    #nub = SocketActorNub(poller, 'apogee-ql.apo.nmsu.edu', 18281,
    #nub = SocketActorNub(poller, 'matt-1.astro.virginia.edu', 33221,
    nub = SocketActorNub(poller, cfg['host'], cfg['port'],
                         name=name, encoder=e, decoder=d,
                         grabCID=True, # the actor spontaneously generates a line we can eat.
                         initCmds=initCmds, # safeCmds=safeCmds,
                         needsAuth=False,
                         logDir=os.path.join(g.logDir, name),
                         debug=3)
    hub.addActor(nub)

def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n
