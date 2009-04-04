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

    # initCmds = ('ping',)
    # safeCmds = r'^\s*status\s*$'

    d = ASCIIReplyDecoder(debug=1)
    e = ASCIICmdEncoder(debug=1)
    dis = SocketActorNub(poller, 'sdssmcp', 31012,
                         name=name, encoder=e, decoder=d,
                         grabCID=True, # the MCP spontaneously generates a line we can eat.
                         # initCmds=initCmds, safeCmds=safeCmds,
                         needsAuth=False,
                         logDir=os.path.join(g.logDir, name),
                         debug=1)
    hub.addActor(dis)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n
