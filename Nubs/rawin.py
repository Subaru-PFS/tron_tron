import Hub
import g
import hub

name = 'rawin'
listenPort = 6090

def acceptStdin(in_f, out_f, addr=None):
    """ Create a command source with the given fds as input and output. """
    
    d = Hub.RawCmdDecoder('gcam', EOL='\r\n', debug=9)
    e = Hub.RawReplyEncoder(keyName='RawTxt', EOL='\n', debug=9)

    c = Hub.StdinNub(g.poller, in_f, out_f,
                     name='TC01.TC01',
                     encoder=e, decoder=d, debug=1)
    c.taster.addToFilter(['gcam', 'na2cam'], [], [])
    hub.addCommander(c)
    
def start(poller):
    stop()
    
    l = Hub.SocketListener(poller, listenPort, name, acceptStdin)
    hub.addAcceptor(l)
    
def stop():
    l = hub.findAcceptor(name)
    if l:
        hub.dropAcceptor(l)
        del l
