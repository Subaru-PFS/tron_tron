import Hub
import hub

name = 'na2cam'

def start(poller):
    stop()

    d = Hub.RawReplyDecoder(EOL='\r', stripChars='\x00\n',
                           debug=9)
    e = Hub.RawCmdEncoder(EOL='\r', debug=9)
    nub = Hub.RawActorNub(poller, 'tccserv35m', 2700,
                          name=name, encoder=e, decoder=d,
                          oneAtATime=True, debug=9)
    hub.addActor(nub)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n
