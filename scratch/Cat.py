#!/usr/bin/env python

import os
import select
import socket
import sys
import time

import CPL
import Hub
import Nub

class Cat(Nub.ActorNub):
    def __init__(self, poller, hub, **argv):
        """ Set up to copy from inport to outport. """

        Nub.ActorNub.__init__(self, poller, **argv)
        self.hub = hub
        self.EOL = '\n'
        
    def copeWithInput(self, s):
        """ Incorporate new input: buffer it, then extract and operate each complete new command.

        Args:
           s   - the new, but still unbuffered, input.

        Returns:
           Nothing.

        """

        if self.debug:
            CPL.log('Nub.copeWithInput', "CommanderNub %s read: %s" % (self.name, s))

        # Buffer the new data.
        self.inputBuffer += s

        # Find and execute _every_ complete input.
        # The only time this function gets called is when new input comes in, so we
        # have no reliable mechanism for deferring input.
        #
        while 1:
            cmd, leftover = self.decoder.decode(self.inputBuffer)
            if cmd == None:
                break

            self.inputBuffer = leftover

            self.hub.sendCommand(Hub.Command.Command(self.ID, None, None, "hub", cmd.cmd))
            self.queueForOutput("%s %s : %s%s" % \
                                (cmd.c_mid, cmd.c_cid,
                                 "got=%r" % (cmd.cmd),
                                 self.EOL))
            
                        
    def XXcopeWithInput(self, s):
        CPL.log("Cat.copeWithInput", "read: %s" % (s,))

        while 1:
            d = self.decoder.decode(s)
            if d == None:
                return

            r = Hub.Reply.Reply(d.c_mid, d.c_cid, ':', (('time', (time.time())), ('read', (c.cmd))))
            re = self.encoder.encode(r)

            self.queueForOutput(re)
            
