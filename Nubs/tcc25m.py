import os.path

from Hub.Command.Encoders.ASCIICmdEncoder import ASCIICmdEncoder
from Hub.Reply.Decoders.ASCIIReplyDecoder import ASCIIReplyDecoder
from Hub.Nub.TCCShellNub import TCCShellNub

import g
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
                'show scale',
                'mir status')

    safeCmds = r"(^show )|(status$)"
    
    d = ASCIIReplyDecoder(EOL='\r',
                          stripChars='\n',
                          CIDfirst=False,
                          debug=1
                          )
    e = ASCIICmdEncoder(EOL='\r', debug=1, CIDfirst=False)
    tcc = TCCShellNub(poller, ['/usr/bin/ssh', '-1',
                               '-e', 'none', '-a', '-x',
                               '-i', os.path.expanduser('~/.ssh/tron'), 
                               '-T', 'tccuser@tcc25m'],
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

