#!/usr/local/bin/python

import fcntl
import os
import sys

import CPL
import IO
import Hub

import g

CPL.log.setLogfile('logs/cat.log', truncate=True)
CPL.log.setID('cat')

g.poller = IO.PollHandler.PollHandler()

g.KVs = Hub.KVDict.KVDict()
g.xids = CPL.ID.ID()
g.listeners = {}
g.hubcmd = None
g.hubcmd = Hub.Command.Command('cat', 0, 0, 'cat', None, actorCid=0, actorMid=0)

d = Hub.Reply.ASCIIReplyDecoder(EOL='\n', CIDfirst=True, debug=5)
e = Hub.Command.ASCIICmdEncoder(EOL='\n', useTarget=True, debug=5)
hub = Hub.Nub.SocketActorNub(g.poller, 'localhost', 6097,
                             name='recat', encoder=e, decoder=d, debug=5)

in_f = sys.stdin
out_f = sys.stdout
fcntl.fcntl(in_f.fileno(), fcntl.F_SETFL, os.O_NDELAY)
fcntl.fcntl(out_f.fileno(), fcntl.F_SETFL, os.O_NDELAY)

c = Hub.Cat.Cat(g.poller, hub, in_f=in_f, out_f=out_f,
                encoder=Hub.Reply.ASCIIReplyEncoder(simple=True, noSrc=True),
                decoder=Hub.Command.ASCIITargetCmdDecoder(debug=5), debug=5)
g.listeners['cat'] = c


g.poller.run()

