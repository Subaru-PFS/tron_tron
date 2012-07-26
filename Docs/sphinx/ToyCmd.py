#!/usr/bin/env python

import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types

from opscore.utility.qstr import qstr

class ToyCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are automatically registered with the actor's parser,
        # which will call the associated methods when matched. The
        # callbacks will be passed a single argument, the parsed and
        # typed command.
        #
        self.vocab = [
            ('ping', '', self.ping),
            ('status', '', self.status),
            ('doSomething', '<cnt> [delay]', self.doSomething),
            ('passAlong', '<actor> <cmd>', self.passAlong),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("toy_toy", (1, 1),
                                        keys.Key("actor", types.String(), help="Another actor to command"),
                                        keys.Key("cmd", types.String(), help="A command string"),
                                        keys.Key("cnt", types.Int(), help="A count of things to do"))
                                        keys.Key("delay", types.Float(), help="Seconds to delay"))
        #
    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        # 
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report status and version; obtain and send current data"""

        self.actor.sendVersionKey(cmd)

        cmd.inform('text="still nothing to say"')
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

