import Hub
import g
import hub

name = 'cat'

def start(poller):
    stop()

    reload(Hub)
    
    d = Hub.ASCIIReplyDecoder()
    e = Hub.ASCIICmdEncoder()
    n = Hub.ShellNub(poller, ['/home/cloomis/mc/TestCat.py'], name=name,
                     encoder=e, decoder=d, debug=5)
    hub.addActor(n)

    return n

def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n
        
                

