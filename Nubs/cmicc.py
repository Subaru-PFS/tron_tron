import time

import Hub
import hub

name = 'CM01.CM01'
host = 'cormass-tcs.apo.nmsu.edu'
port = 3001

def stop():
    n = hub.findCommander(name)
    if n:
        hub.dropCommander(n)
        del n

def start(poller):
    stop()

    d = Hub.RawCmdDecoder('cm', EOL='\r', debug=9)
    e = Hub.RawReplyEncoder(keyName='RawTxt', EOL='\n', debug=9)
    nub = Hub.SocketCommanderNub(poller, host, port,
                       name=name, encoder=e, decoder=d,
                       debug=9)
    nub.taster.setFilter(['cm'], [], [])
    hub.addCommander(nub)
    
