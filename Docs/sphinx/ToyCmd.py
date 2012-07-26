#!/usr/bin/env python

import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types

from opscore.utility.qstr import qstr

class ToyCmd(object):

    def __init__(self, actor):
        # This is essential:
        self.actor = actor

        # Define some typed command arguments. [Can't say I like these being global to all commands. -- CPL]
        self.keys = keys.KeysDictionary("toy_toy", (1, 1),
                                        keys.Key("cartridge", types.Int(), help="A cartridge ID"),
                                        keys.Key("actor", types.String(), help="Another actor to command"),
                                        keys.Key("cmd", types.String(), help="A command string"),
                                        keys.Key("cnt", types.Int(), help="A count of things to do"),
                                        keys.Key("delay", types.Float(), help="Seconds to delay"))
        #
        # Declare commands
        #
        self.vocab = [
            ('ping', '', self.ping),
            ('status', '', self.status),
            ('doSomething', '<cnt> [delay]', self.doSomething),
            ('passAlong', '<actor> <cmd>', self.passAlong),
        ]

    def ping(self, cmd):
        '''Query the actor for liveness/happiness.'''

        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        '''Report status and version; obtain and send current data'''

        self.actor.sendVersionKey(cmd)
        self.doStatus(cmd, flushCache=True)

    def doStatus(self, cmd=None, flushCache=False, doFinish=True):
        '''Report full status'''

        if not cmd:
            cmd = self.actor.bcast

        keyStrings = ['text="nothing to say, really"']
        keyMsg = '; '.join(keyStrings)

        cmd.inform(keyMsg)
        cmd.diag('text="still nothing to say"')
        cmd.finish()

    def doSomething(self, cmd):
        """ Do something pointless. """

        cnt = cmd.cmd.keywords["cnt"].values[0]
        delay = cmd.cmd.keywords["delay"].values[0] if "delay" in cmd.cmd.keywords else 0.0
        for i in range(cnt):
            cmd.inform('cnt=%d' % (i))
            if delay:
                time.sleep(delay)
        cmd.finish()

    def passAlong(self, cmd):
        """ Pass a command along to another actor. """

        actor = cmd.cmd.keywords["actor"].values[0]
        cmdString = cmd.cmd.keywords["cmd"].values[0]

        cmdVar = self.actor.cmdr.call(actor=actor, cmdStr=cmdString,
                                      forUserCmd=cmd, timeLim=30.0)
        if cmdVar.didFail:
            cmd.fail('text=%s' % (qstr('Failed to pass %s along to %s' % (cmdStr, actor))))
        else:
            cmd.finish()

