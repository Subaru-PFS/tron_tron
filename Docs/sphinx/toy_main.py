#!/usr/bin/env python

# Needs to be imported early: sets the default log formatter.
import opscore.utility.sdss3logging

from twisted.internet import reactor

import opscore.actor.model
import actorcore.Actor


class Toy(actorcore.Actor.Actor):
    def __init__(self, name, productName=None, configFile=None, debugLevel=30):
        # This sets up the connections to/from the hub, the logger, the twisted reactor.
        #
        actorcore.Actor.Actor.__init__(self, name, productName=productName, configFile=configFile)

        # This is parsed to give the version string.
        self.headURL = '$HeadURL: svn+ssh://sdss3svn@sdss3.org/repo/ops/actors/apoActor/trunk/python/apoActor/apoActor_main.py $'

        self.logger.setLevel(debugLevel)
        self.logger.propagate = True

        # Explicitly load other actor models. We usually need these for FITS headers.
        #
        self.models = {}
        for actor in ["mcp", "guider", "platedb", "tcc"]:
            self.models[actor] = opscore.actor.model.Model(actor)

        # Finish by starting the twisted reactor
        #
        self.run()

    def periodicStatus(self):
        '''Run some command periodically'''

        self.callCommand('status')
        reactor.callLater(int(self.config.get(self.name, 'updateInterval')), self.periodicStatus)

    def connectionMade(self):
        '''Runs this after a connection is made from the hub'''

        # Schedule an update.
        #
        reactor.callLater(3, self.periodicStatus)

#
# To work
#
if __name__ == '__main__':
    toy = Toy('toy', 'toyActor')
