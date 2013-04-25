import os.path

""" The core connection functions for a "standard" Nub for an actor which:
     - uses an ASCII Command encoder (i.e. the hub _sends_ commands to the actor)
     - uses an ASCII Reply decoder (i.e. the hub receives replies from the actor)
     - is connected to with a TCP socket.
     - identifies itself when poked with a 'ping' command
     - return _all_ keywords when sent a 'status' command

    For very historic reasons, the interface is functional, and not OO. This should probably be
    changed: the individual nubs could just subclass this, and be entirely descibed via configuration.
    But be careful about overdoing cleanup: we might need specialized transport fiddles to handle, say, 
    binary protocols.
"""

from Hub.Command.Encoders.ASCIICmdEncoder import ASCIICmdEncoder
from Hub.Reply.Decoders.ASCIIReplyDecoder import ASCIIReplyDecoder
from Hub.Nub.SocketActorNub import SocketActorNub

import CPL.cfg
from CPL import qstr
import hub
import g

def start(poller, name, initCmds=None, 
          encoderDebug=1,
          decoderDebug=1,
          nubDebug=1,
          hostname=None, port=None):

    cfg = CPL.cfg.get('hub', 'actors', doFlush=True)[name]
    stop(name)

    if hostname == None:
        hostname = cfg['host']
    if port == None:
        port = cfg['port']

    g.hubcmd.inform('text="connecting to MHS Nub %s at %s:%s"' % (name, hostname, port))

    if initCmds == None:
        initCmds = ('ping',
                    'status')
    # safeCmds = r'^\s*info\s*$'

    d = ASCIIReplyDecoder(debug=decoderDebug)
    e = ASCIICmdEncoder(sendCommander=True, useCID=False, 
                        debug=encoderDebug)

    try:
        nub = SocketActorNub(poller, hostname, port,
                             name=name, encoder=e, decoder=d,
                             grabCID=True,
                             initCmds=initCmds, # safeCmds=safeCmds,
                             needsAuth=False,
                             logDir=os.path.join(g.logDir, name),
                             debug=nubDebug)
    except Exception, e:
        g.hubcmd.warn('text=%s' % (qstr("failed to start MHS Nub  %s at %s:%s: %s" % (name, hostname, port, e))))
        raise

    hub.addActor(nub)
    
def stop(name):
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n
