#!/usr/bin/env python

""" A "ping" command, which tests end-to-end connections through the hub. """

import sys
import time

import client
import CPL
import Actor
import Parsing

class Ping(Actor.Actor):
    """ 
    """
    
    def __init__(self, **argv):
        Actor.Actor.__init__(self, 'ping', **argv)

    def _parse(self, cmd):
        """ We do our own parsing. """
        
        matches, unmatched, leftovers = cmd.match([('count', int),
                                                   ('delay', float)])

        keys = []
        keyN = 1
        for s in leftovers:
            keys.append("key%03d=%s" % (keyN, CPL.qstr(s)))
            keyN += 1

        matches['keyString'] = '; '.join(keys)
        self.doPing(cmd, **matches)

    def doPing(self, cmd,
               count=1, delay=0.0,
               keyString=""):

        """ Send a given number of replies.

        Args:
           cmd        - the command to respond to
           count      - the number of replies to send
           keyString  - the keys to return
        """

        cmd.warn("pingCount=%d; pingDelay=%0.2f" % (count, delay))
        
        n = 1
        while n < count:
            cmd.respond(keyString)
            n += 1
            if delay > 0.00001:
                time.sleep(delay)
                
        cmd.finish(keyString)
            
    
# Start it all up.
#
def main(name, eHandler=None, debug=0, test=False):
    actor = Ping(debug=debug)
    actor.start()

    client.run(name=name, cmdQueue=actor.queue,
               background=False, debug=debug, cmdTesting=test)
    CPL.log('ping.main', 'DONE')

if __name__ == "__main__":
    main('ping', debug=1)
