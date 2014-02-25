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
          argHost=None, argPort=None):

    """ Start a managed MHS actor, where we specify the host:port

    But we want to apply configuration control for production. So here are the rules:

     a. the actor/user can send 'startNub actorName host:port'
     b. the hub's configuration can contain an actors[actorName] with host and port item.
     c. the actors[actorName] dict can also contain a boolean 'fixed' item.

    If fixed is True, then the configuration file cannot be overridden. If startNub specifies
    host and/or port, they _must_ match the hub configuration.

    Otherwise, if the actor sends host:port, those values are used, and any conflict generates only
    a warning.

    Otherwise the config is used.
    """

    try:
        cfg = CPL.cfg.get('hub', 'actors', doFlush=True)[name]
    except:
        cfg = dict()

    fixed = cfg.get('fixed', False)
    cfgHost = cfg.get('host', None)
    cfgPort = cfg.get('port', None)
    if fixed:
        if (argHost is not None and argHost != cfgHost) or (argPort is not None and argPort != cfgPort):
            g.hubcmd.warn('text="tron host:port configuration for %s is fixed: ignoring conflicting user-specified address"' 
                          % (name))

        hostname = cfgHost
        port = cfgPort
        if hostname is None or port is None:
            raise RuntimeError("tron host:port configuration for %s is fixed, but the address is not complete (%s:%s)" % 
                               (name, hostname, port))
    else:
        if (cfgHost is not None and argHost != cfgHost) or (cfgPort is not None and argPort != cfgPort):
            g.hubcmd.warn('"user and tron addresses for %s differ, using user-specified address"' % (name))

        hostname = argHost if argHost else cfgHost
        port = argPort if argPort else cfgPort
        if hostname is None or port is None:
            raise RuntimeError("address for %s is not fully specified (%s:%s)" % 
                               (name, hostname, port))

    g.hubcmd.inform('text="connecting to MHS Nub %s at %s:%s"' % (name, hostname, port))

    stop(name)

    if initCmds is None:
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
