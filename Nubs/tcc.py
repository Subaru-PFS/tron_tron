import os.path

import g
import Hub
import hub
import IO

name = 'tcc'

def start(poller):

    stop()

    initCmds = ('show version',
                'show users',
                'show time',
                'show status',
                'show inst/full',
                'show object/full',
                'show axisconfig',
                'show focus',
                'axis status',
                'mir status')

    safeCmds = r"(^show )|(status$)"
    
    d = Hub.ASCIIReplyDecoder(EOL='\r',
                              stripChars='\n',
                              debug=1)
    e = Hub.ASCIICmdEncoder(EOL='\r', debug=1)
    tcc = Hub.TCCShellNub(poller, ['/usr/bin/ssh', '-1',
                                   '-e', 'none', '-a', '-x',
                                   '-i', '/home/apotop/.ssh/mc', 
                                   '-T', 'tccuser@tcc35m'],
                          initCmds=initCmds, safeCmds=safeCmds,
                          needsAuth=True,
                          name=name, encoder=e, decoder=d,
                          logDir=os.path.join(g.logDir, name),
                          debug=1)
    hub.addActor(tcc)
    
def stop():
    n = hub.findActor(name)
    if n:
        hub.dropActor(n)
        del n

