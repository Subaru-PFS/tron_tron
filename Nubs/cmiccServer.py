import os
import time

import Hub
import hub
import CPL
import g

name = 'CM01.CM01'
listenPort = 6563

def acceptCMICC(in_f, out_f, addr=None):
    stopICC()
    
    d = Hub.RawCmdDecoder('cm', EOL='\r', debug=9)
    e = Hub.RawReplyEncoder(keyName='RawTxt', EOL='\f', debug=9)
    nub = Hub.StdinNub(g.poller, in_f, out_f,
                       name=name, encoder=e, decoder=d,
                       logDir=os.path.join(g.logDir, name),
                       debug=9)
    nub.taster.setFilter(['cm'], [], [])
    hub.addCommander(nub)
    
def stopICC():
    n = hub.findCommander(name)
    if n:
        hub.dropCommander(n)
        del n

def start(poller):
    stop()

    lt = Hub.SocketListener(poller, listenPort, name, acceptCMICC)
    hub.addAcceptor(lt)
    
def stop():
    n = hub.findAcceptor(name)
    if n:
        hub.dropAcceptor(n)
        del n
        time.sleep(0.5)
