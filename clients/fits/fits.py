#!/usr/bin/env python

""" The fits command.

   fits start <inst>
   fits finish <inst> in-file out-file
   
"""

import time

import client
import Command
import Actor
import CPL.log as log

class FITSActor(Actor.Actor):
    def __init__(self, **argv):
        Actor.Actor.__init__(self, 'fits', debug=3)
        
        # Indexed by instrument
        self.headers = {}

        self.helpText = ("fits COMMAND",
                         "   COMMAND is one of:",
                         "     help                - this text.",
                         "     start INST          - create a header for the given instrument.",
                         "     annotate INST in-file out-file",
                         "                         - merge our header for the given instrument with that in in-file",
                         "     create INST in-file out-file",
                         "                         - create a header for the given instrument for data in in-file",
                         )

    def parse(self, cmd):
        try:
            self._parse(cmd)
        except Exception, e:
            cmd.fail('fitsTxt=%s' % qstr(e, tquote='"'))
            CPL.log("fits", "exception=%s" % (e))
            return

    def _parse(self, cmd):
        """
        """

        if self.debug >= 0:
            CPL.log("FITSHandler", "new command: %s" % (cmd.raw_cmd))

        cmdWords = cmd.keys
        if length(cmdWords) == 0:
            cmd.fail('fitsTxt="Empty command ignored"')
            return

        cmdWord = cmdWords[0]
        if cmdWord == 'help':
            self.help(cmd)
            return
        
        if cmdWord == 'status':
            self.status(cmd)
            return
        
        if cmdWord == 'start':
            if length(cmdWords) != 2:
                cmd.fail('fitsTxt="start command takes (only) an instrument name as an argument."')
                return
            inst = self.normalizeInstrument(cmdWords[1])

            if self.headers.has_key(inst):
                cmd.warn('fitsTxt="overwriting header for %s"' % (inst))

            self.startHeader(cmd, inst)
            return

    def status(self, cmd):
        """
        """

        CPL.log('status', "starting status")
        
        for i in self.headers.keys():
            cmd.respond('%sFITS=%d' % (i, 0))
        cmd.finish('')

    def start(self, cmd, inst):
        """ Allocate a new header for the given instrument
        
    def normalizeInstrument(self, instName):
        return instName.lower()
    
# Start it all up.
#

def main(name, handler=None, debug=0, test=False):
    if handler == None:
        handler = FITSActor(debug=1)
    handler.start()
    client.run(name=name, cmdQueue=handler.queue, background=test, debug=3, cmdTesting=test)

if __name__ == "__main__":
    main('fits', debug=0)
