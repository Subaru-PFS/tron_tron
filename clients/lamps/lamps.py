#!/usr/bin/env python

""" The lamps command.

   lamps list
   lamps on a,b,c
   lamps off
   lamps off a,b
"""

import time

import client
import Command
import Actor
import CPL.log as log


class LampsActor(Actor.Actor):
    def __init__(self, **argv):
        Actor.Actor.__init__(self, 'lamps', debug=9)
        
    def parse(self, cmd):
        """
        """

        if self.debug >= 0:
            CPL.log("LampsHandler", "new command: %s" % (cmd.raw_cmd))
            
        # Look for the essential arguments. The instrument name and exactly
        # one of the commands.
        #
        req, notMatched, opt, leftovers = cmd.coverArgs([], ['list', 'on', 'off'])

        if len(opt) != 1:
            cmd.fail('errtxt="exactly one lamps command is needed"')
            return
        command = opt.keys()[0]

# Start it all up.
#

def main(name, eHandler=None, debug=0, test=False):
    if eHandler == None:
        eHandler = LampsActor(debug=9)
    eHandler.start()
    client.run(name=name, cmdQueue=eHandler.queue, background=test, debug=5, cmdTesting=test)

def test():
    global mid
    mid = 1
    main('lamps', test=True)

def tc(s):
    global mid
    
    client.cmd("APO CPL %d 0 %s" % (mid, s))
    mid += 1
    
if __name__ == "__main__":
    main('lamps', debug=0)
