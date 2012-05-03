""" tcc2guider.py -- accept commands from the tcc, and send them to the guider Actor.

The guider actor will generate, among other things, some special keywords formatted to look just the
GImCtrl output. These, and only these, we unbundle and return to the tcc.

"""

import os
import time

import g
import Hub.Command.Decoders.RawCmdDecoder as RawDecoder
from Hub.Reply.Encoders.RawReplyEncoder import RawReplyEncoder
from Hub.Nub.Commanders import StdinNub
from Hub.Nub.Listeners import SocketListener

import hub

name = 'TC01.gcam'
host = 'localhost'
listenPort = 3012

def acceptNewTcc(in_f, out_f, addr=None):
    d = RawDecoder('guider', cmdWrapper="tccCmd", EOL='\r',
				   stripChars='\n',
				   debug=7)
    e = RawReplyEncoder(keyName='txtForTcc', EOL='\r', debug=7)
    nub = StdinNub(g.poller, in_f, out_f,
                   name=name, encoder=e, decoder=d,
                   logDir=os.path.join(g.logDir, name),
                   debug=6, writeSize=100)
    
    nub.taster.setFilter(['guider'], ['guider'], [])
    hub.addCommander(nub)
    
def start(poller):
    stop()
    
    l = SocketListener(poller, listenPort, name, acceptNewTcc)
    hub.addAcceptor(l)
    
    time.sleep(1)

def stop():
    l = hub.findCommander(name)
    if l:
        hub.dropCommander(l)
        del l

    l = hub.findAcceptor(name)
    if l:
        hub.dropAcceptor(l)
        del l

