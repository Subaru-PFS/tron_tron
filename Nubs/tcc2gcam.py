""" tcc2gcam.py -- accept commands from the tcc, and send them to the gcam Actor.

The gcam actor will generate, among other things, some special keywords formatted to look just the
GImCtrl output. These, and only these, we unbundle and return to the tcc.

"""

import time

import Hub
import hub

name = 'TC01.TC01'
host = 'apots2.apo.nmsu.edu'
port = 3012

def stop():
    n = hub.findCommander(name)
    if n:
        hub.dropCommander(n)
        del n

def start(poller):
    stop()

    d = Hub.RawCmdDecoder('gcam', EOL='\r', debug=9)
    e = Hub.RawReplyEncoder(keyName='RawTxt', EOL='\r', debug=9)
    nub = Hub.SocketCommanderNub(poller, host, port,
                       name=name, encoder=e, decoder=d,
                       debug=9)
    nub.taster.setFilter(['gcam'], ['gcam'], [])
    hub.addCommander(nub)
    
