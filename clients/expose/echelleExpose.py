#!/usr/bin/env python

""" The expose command.

   exposeInst CMD EXPOSE-ARGS INST-ARGS

   CMD:
      OBJECT itime=S PATH=P NAME=N SEQ=
      
   expose object itime=S
      [ may add "arc" and/or "flat" ]
   expose dark itime=S
   expose bias

   expose stop
   expose abort

   expose pause
   expose resume

      path="p/a/t/h"
      name="base."
      seq="0003"

   The final path will be under a system-specified root directory. Each _program_
   has is own root directory, under which any path can be used. If these arguments
   are not passed in, the previous values from the given program+instrument are used.

   Exposures and paths are maintained per-(program+instrument):
   Different programs obviously want separate pathnames. If two users within a given program
   want to use the same instrument, we assume they want to share paths, but if they are using
   two different instruments they most likely want different file name sets.
   
"""

import inspect
import pprint
import sys
import time
import traceback

import client
import Command
import Actor
import ExpPath
import InstExposure
from Exposure import ExpSequence
import CPL


class EchelleExposureActor(InstExposure.InstExposure):
    def __init__(self, **argv):
        InstExposure.InstExposure.__init__(self, 'echelleExpose', debug=1)
        
        self.instName = 'echelle'

        self.helpText = ("echelleExpose COMMAND [ARGS]",
                         "   COMMAND is one of:",
                         "     help         - you got it!",
                         "     status       - generate the appropriate keywords.",
                         "",
                         "     pause        - pause active sequence, if possible",
                         "     resume       - resume paused sequence",
                         "     stop         - immediately readout and save current exposure, if possible. Stop sequence.",
                         "     abort        - immediately stop and DISCARD current exposure, if possible. Stop sequence.",
                         "",
                         "     bias [n=N] [PATH-ARGS]",
                         "     dark time=S [n=N] [PATH-ARGS]",
                         "     object time=S [n=N] [PATH-ARGS]",
                         "     flat time=S [n=N] [PATH-ARGS]",
                         "       Take N exposures of the given type. If given, adjust or set the file name, number, or path",
                         "       to the given PATH-ARGS, which are:",

                         "     name=NAME    - the leftmost part of the filename. Can include a unix path e.g. name='night1/cals.'",
                         "     seq=N        - the exposure number to start the sequence at. Can be 'next', which is the default.",
                         "     places=N     - the number of digits to use for the sequence number. Default=4",
                         "     suffix=TXT   - how to finish the filename off. e.g. suffix='.fits'. Default='.fits'",
                         "",
                         "     All are 'sticky': once specified, the same program using the same instrument would later get the",
                         "     same values. Well, the sequence number would be incremented.",
                         "     The APO root directory is currently /export/images/PROGRAMNAME on tycho, where ",
                         "     PROGRAMNAME is the assigned schedule (and login) ID.",
                         "",
                         "     So if a PU04 user sent:",
                         "       echExpose object time=10 n=2 name='night1/cals.seq=14 places=4",
                         "     PU04 would get two files:",
                         "       tycho:/export/images/PU04/night1/cals.0014.fit and tycho:/export/images/PU04/night1/cals.0015.fit",
                         "     And if another PU04 user then sent:",
                         "       echExpose bias name='night1/bias.'",
                         "     that user would get:",
                         "       tycho:/export/images/PU04/night1/bias.0016.fit",
                         "")
                         

    def _parse(self, cmd):
        """
        """

        if self.debug >= 0:
            CPL.log("EchelleExposureHandler", "new command: %s" % (cmd.raw_cmd))

        anytimeCmds = ('help', 'status', 'getPath', 'setPath')
        newExpCmds = ('object', 'flat', 'dark', 'bias')
        expCmds = ('stop', 'abort', 'pause', 'resume', 'zap')
        commands = anytimeCmds + newExpCmds + expCmds
        
        # Look for exactly one of the commands.
        #
        req, notMatched, leftovers = cmd.match([(c, None) for c in commands])
                                                    
        if self.debug >= 0:
            CPL.log("ExposureHandler", "parsed args: %s" % (req))
            
        if req.has_key('help'):
            self.help(cmd)
            return
        
        if req.has_key('status'):
            self.status(cmd)
            return
        
        command = None
        for expCmd in 'flat', 'object', 'dark', 'bias', \
                'pause', 'resume', 'stop', 'abort', 'zap', \
                'getPath', 'setPath':
            if req.has_key(expCmd):
                if command != None:
                    cmd.fail('exposeTxt="only one expose command can be run."')
                    return
                command = expCmd
        if command == None:
            cmd.fail('exposeTxt="one expose command must be run."')
            return

        # OK, split ourselves into operations which do and do not act on an existing exposure.
        #
        exp = self.sequence

        # Define the image path for future exposures.
        #
        if command == 'setPath':
            if exp != None:
                cmd.fail('exposeTxt="cannot modify the path while an exposure is active"')
                return
            self.setPath(cmd)
            self.returnKeys(cmd)
            cmd.finish('')
            return
        
        elif command == 'getPath':
            self.returnKeys(cmd)
            cmd.finish('')
            return
        
        elif command in ('stop', 'abort', 'pause', 'resume', 'zap'):
            if exp == None:
                cmd.fail('exposeTxt="no %s exposure is active"' % (self.instName))
                return
            else:
                # Only let the exposure owner or any APO user control an active exposure.
                #
                if exp.cmd.program() != cmd.program() and cmd.program() != 'APO':
                    cmd.fail('exposeTxt="the %s exposure belongs to "' % (self.instName,
                                                                            cmd.cmdrName))
                    return

                exec("exp.%s(cmd)" % (command))
                return

        elif command in ('object', 'flat', 'bias', 'dark'):
            if exp != None:
                cmd.fail('exposeTxt="cannot start a new %s exposure while another is active"' % (self.instName))
                return

            # req, notMatched, opt, leftovers = cmd.coverArgs(['n'])
            req, notMatched, leftovers = cmd.match([('n', int),
                                                    ('startNum', int),
                                                    ('totNum', int)])
            
            cnt = req.get('n', 1)
            if not cnt > 0:
                cmd.fail('exposeTxt="argument to \'n\' option must be a positive integer"')
                return
            
            seqArgv = {}
            if 'startNum' in req:
                seqArgv['startNum'] = req['startNum']
            if 'totNum' in req:
                seqArgv['totNum'] = req['totNum']

            path = self.setPath(cmd)
            exp = ExpSequence(self, cmd, self.instName, command, path, cnt,
                              debug=1,
                              **seqArgv)
            self.lastSequence = self.sequence
            self.sequence = exp
            exp.run()
        else:
            cmd.fail('exposeTxt="command %s has not even been imagined"' % (CPL.qstr(command, tquote="'")))
            return

        return "exposeID=%s,%s" % (CPL.qstr(cmd.program()), CPL.qstr(self.instName))

# Start it all up.
#

def main(name, eHandler=None, debug=0, test=False):
    if eHandler == None:
        eHandler = EchelleExposureActor(debug=1)
    eHandler.start()
    client.run(name=name, cmdQueue=eHandler.queue, background=test, debug=1, cmdTesting=test)

if __name__ == "__main__":
    main('echelleExpose', debug=0)
