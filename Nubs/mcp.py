import os.path

from Hub.Command.Encoders.ASCIICmdEncoder import ASCIICmdEncoder
from Hub.Reply.Decoders.ASCIIReplyDecoder import ASCIIReplyDecoder
from Hub.Nub.SocketActorNub import SocketActorNub
from Hub.Nub.Listeners import SocketListener
import hub
import g

name = 'mcp'

def start(poller):
    stop()

    initCmds = ('info',)
    safeCmds = r'^\s*info\s*$'

    d = ASCIIReplyDecoder(debug=1)
    e = ASCIICmdEncoder(debug=1)
    nub = SocketActorNub(poller, 'sdssmcp', 31012,
                         name=name, encoder=e, decoder=d,
                         grabCID=True, # the MCP spontaneously generates a line we can eat.
                         initCmds=initCmds, safeCmds=safeCmds,
                         needsAuth=False,
                         logDir=os.path.join(g.logDir, name),
                         debug=1)
    hub.addActor(nub)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n
