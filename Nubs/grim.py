import Hub
import g
import hub
import time
import CPL

""" The grim ICC connects itself to the hub. It uses two sockets, one for receiving commands, the
other for sending replies. Both connections use the old hub's binary protocol.

   The other difficulty is that the ICC sends images back inline. We don't really want to 
"""


name = 'grim'

listenPort1 = 6003
listenPort2 = 6004

port1 = None
port2 = None

def acceptGrim1(in_f, out_f, addr=None):
    """ Create a command source with the given fds as input and output. """
    
    global port1
    global port2
    
    CPL.log("grim.accept1", "accept1")

    port1 = in_f
    if port2 != None:
        acceptGrim(port1, port2, addr=addr)
        port1 = port2 = None

def acceptGrim2(in_f, out_f, addr=None):
    """ Create a command source with the given fds as input and output. """
    
    global port1
    global port2

    CPL.log("grim.accept2", "accept")
    
    port2 = out_f
    if port1 != None:
        acceptGrim(port1, port2, addr=addr)
        port1 = port2 = None

def acceptGrim(in_f, out_f, addr=None):
    """ Create an ActorNub  with the given fds as input and output. """

    safeCmds = '^\s*status:\s*$'
    initCmds = ('status:',)
    
    nubID = g.nubIDs.gimme()
    
    d = Hub.BinaryReplyDecoder(debug=0, scratchDir='/export/images/scratch',
                               BZERO=22768.0, signFlip=True)
    e = Hub.BinaryCmdEncoder(debug=1)
    c = Hub.ActorNub(g.poller,
                     in_f=in_f, out_f=out_f,
                     name=name,
                     safeCmds=safeCmds,
                     needsAuth=True,
                     encoder=e, decoder=d, debug=1)
    hub.addActor(c)

def start(poller):
    reload(Hub)

    stop()

    lt = Hub.SocketListener(poller, listenPort1, "%s1" % (name), acceptGrim1)
    hub.addAcceptor(lt)
    lt = Hub.SocketListener(poller, listenPort2, "%s2" % (name), acceptGrim2)
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
