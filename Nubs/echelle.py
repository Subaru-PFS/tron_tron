import Hub
import g
import hub

import os
import time

""" The echelle ICC connects itself to the hub. It uses two sockets, one for receiving commands, the
other for sending replies. Both connections use the old hub's binary protocol.

   The other difficulty is that the ICC sends images back inline. We don't really want to 
"""


name = 'echelle'

listenPort1 = 6007
listenPort2 = 6008

port1 = None
port2 = None

def acceptEchelle1(in_f, out_f, addr=None):
    """ Create a command source with the given fds as input and output. """
    
    global port1
    global port2
    
    port1 = in_f
    if port2 != None:
        acceptEchelle(port1, port2, addr=addr)
        port1 = port2 = None

def acceptEchelle2(in_f, out_f, addr=None):
    """ Create a command source with the given fds as input and output. """
    
    global port1
    global port2

    port2 = out_f
    if port1 != None:
        acceptEchelle(port1, port2, addr=addr)
        port1 = port2 = None

def acceptEchelle(in_f, out_f, addr=None):
    """ Create an ActorNub  with the given fds as input and output. """

    safeCmds = r'^\s*status:\s*$'
    initCmds = ('status:',)
    nubID = g.nubIDs.gimme()
    
    d = Hub.BinaryReplyDecoder(debug=1, scratchDir='/export/images/scratch')
    e = Hub.BinaryCmdEncoder(debug=1)
    c = Hub.ActorNub(g.poller,
                     in_f=in_f, out_f=out_f,
                     name=name,
                     encoder=e, decoder=d,
                     needsAuth=True,
                     logDir=os.path.join(g.logDir, name),
                     initCmds=initCmds, safeCmds=safeCmds,
                     readSize=262144, debug=1)
    hub.addActor(c)

def start(poller):
    reload(Hub)

    stop()

    lt = Hub.SocketListener(poller, listenPort1, "%s1" % (name), acceptEchelle1)
    hub.addAcceptor(lt)
    lt = Hub.SocketListener(poller, listenPort2, "%s2" % (name), acceptEchelle2)
    hub.addAcceptor(lt)

def stop():
    for i in 1,2:
        a = hub.findAcceptor("%s%d" % (name, i))
        if a:
            hub.dropAcceptor(a)
            del a
            time.sleep(0.5)
            
    a = hub.findActor(name)
    if a:
        hub.dropActor(a)
        del a
