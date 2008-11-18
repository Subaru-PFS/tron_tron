#!/usr/bin/env python

""" The expose command.

   expose inst=XXX CMD EXPOSE-ARGS INST-ARGS

   CMD:
      OBJECT itime=S PATH=P NAME=N SEQ=
      
   expose inst=XXX object itime=S
      [ may add "arc" and/or "flat" ]
   expose inst=XXX dark itime=S
   expose inst=XXX bias

   expose inst=XXX stop
   expose inst=XXX abort

   expose inst=XXX pause
   expose inst=XXX resume

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
from Exposure import ExpSequence
import CPL


class ExposureActor(Actor.Actor):
    def __init__(self, **argv):
        Actor.Actor.__init__(self, 'expose', debug=1)
        
        self.knownInstruments = ('dis', 'echelle', 'grim', 'tspec')

        # Indexed by instrument
        self.openExposures = {}

        # Indexed by program+instrument
        self.knownExpPaths = {}

        self.helpText = ("expose inst=INSTNAME COMMAND [ARGS]",
                         "   inst must be one of: %s" % (", ".join(self.knownInstruments)),
                         "   COMMAND is one of:",
                         "     help         - you got it!",
                         "     status       - generate the appropriate keywords.",
                         "",
                         "     pause        - pause active exposure, if possible",
                         "     resume       - resume paused exposure",
                         "     stop         - immediately readout and save current exposure, if possible. Stop sequence.",
                         "     abort        - immediately stop and DISCARD current exposure, if possible. Stop sequence.",
                         "",
                         "     bias [n=N] [PATH-ARGS]",
                         "     dark time=S [n=N] [PATH-ARGS]",
                         "     object time=S [n=N] [PATH-ARGS]",
                         "     flat time=S [n=N] [PATH-ARGS]",
                         "       Take N exposures of the given type. If given, adjust or set the file name, number, or path",
                         "       to the given PATH-ARGS, which are:",
                         "     dir=DIR      - a directory name. Unix-style. e.g. dir='0603/dis'. This will be under an APO-specified root directory.",
                         "       [Absolute and relative paths are treated the same. dir=/ selects the root directory]",
                         "     name=NAME    - the leftmost part of the filename e.g. name='cals.'",
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
                         "       expose inst=echelle object time=10 n=2 dir='night1/cals' name='flat.' seq=14 places=4",
                         "     PU04 would get two files:",
                         "       tycho:/export/images/PU04/night1/cals/flat.0014.fit and tycho:/export/images/PU04/night1/cals/flat.0015.fit",
                         "     And if another PU04 user then sent:",
                         "       expose inst=echelle bias name='bias.'",
                         "     that user would get:",
                         "       tycho:/export/images/PU04/night1/cals/bias.0016.fit",
                         "")
                         

    def _parse(self, cmd):
        """
        """

        if self.debug >= 0:
            CPL.log("ExposureHandler", "new command: %s" % (cmd.raw_cmd))
            
        # Look for the essential arguments. The instrument name and exactly
        # one of the commands.
        #
        req, notMatched, leftovers = cmd.match([('inst', str),
                                                ('object', None), ('flat', None), ('dark', None), ('bias', None),
                                                ('stop', None), ('abort', None),
                                                ('pause', None), ('resume', None),
                                                ('help', None), ('getPath', None),
                                                ('setPath', None),
                                                ('status', None), ('zap', None)])
                                                    
        if self.debug >= 0:
            CPL.log("ExposureHandler", "parsed args: %s" % (req))
            
        if req.has_key('help'):
            self.help(cmd)
            return
        
        inst = req.get('inst', None)

        # Status can be for all instruments, or one particular instrument.
        if req.has_key('status'):
            self.status(cmd, inst)
            return
        
        command = None
        for expCmd in 'bias', 'flat', 'object', 'dark', \
                'pause', 'resume', 'stop', 'abort', \
                'getPath', 'setPath':
            if req.has_key(expCmd):
                if command != None:
                    cmd.fail('exposeTxt="only one expose command can be run."')
                    return
                command = expCmd
        if command == None:
            cmd.fail('exposeTxt="one expose command must be run."')
            return

        if inst == None:
            cmd.fail('exposeTxt="no instrument specified"')
            return

        inst = inst.lower()
        if not inst in self.knownInstruments:
            cmd.fail('exposeTxt="%s is not a known instrument"' % (CPL.qstr(inst, tquote="'")))
            return

        # OK, split ourselves into operations which do and do not act on an existing exposure.
        #
        exp = self.openExposures.get(inst, None)

        # Define the image path for future exposures.
        #
        if command == 'setPath':
            if exp != None:
                cmd.fail('exposeTxt="cannot modify the path while an exposure is active"')
                return
            self.setPath(cmd, inst)
            self.returnKeys(cmd, inst)
            cmd.finish('')
            return
        
        elif command == 'getPath':
            self.returnKeys(cmd, inst)
            cmd.finish('')
            return
        
        elif command in ('stop', 'abort', 'pause', 'resume', 'zap'):
            if exp == None:
                cmd.fail('exposeTxt="no %s exposure is active"' % (inst))
                return
            else:
                # Only let the exposure owner or any APO user control an active exposure.
                #
                if exp.cmd.program() != cmd.program() and cmd.program() != 'APO':
                    cmd.fail('exposeTxt="the %s exposure belongs to %s.%s"' % (inst,
                                                                            cmd.program(),
                                                                            cmd.username()))
                    return

                exec("exp.%s(cmd)" % (command))
                return

        elif command in ('object', 'flat', 'bias', 'dark'):
            if exp != None:
                cmd.fail('exposeTxt="cannot start a new %s exposure while another is active"' % (inst))
                return

            # req, notMatched, opt, leftovers = cmd.coverArgs(['n'])
            req, notMatched, leftovers = cmd.match([('n', int)])
            
            cnt = req.get('n', 1)
            if not cnt > 0:
                cmd.fail('exposeTxt="argument to \'n\' option must be a positive integer"')
                return
            
            path = self.setPath(cmd, inst)
            exp = ExpSequence(self, cmd, inst, command, path, cnt, debug=1)
            self.openExposures[inst] = exp
            exp.run()
        else:
            cmd.fail('exposeTxt="command %s has not even been imagined"' % (CPL.qstr(command, tquote="'")))
            return

    def status(self, cmd, inst):
        """
        """

        CPL.log('status', "starting status")
        
        sequences = []
        if inst == None:
            sequences = self.openExposures.values()
        else:
            seq = self.openExposures.get(inst, None)
            if seq != None:
                sequences = seq,
            
        CPL.log('status', "status on all of %r" % (sequences))
        for s in sequences:
            CPL.log('status', "status on %r" % (s))
            seqState, expstate = s.getKeys()
            cmd.respond("%s; %s" % (seqState, expstate))
        cmd.finish('')
    
    def getIDKey(self, cmd, inst):
        """ Return the key describing a given command and instrument. """

        return "exposeID=%s,%s" % (CPL.qstr(cmd.program()), CPL.qstr(inst))

    def getPathID(self, cmd, inst):
        return (cmd.program(), inst)

    def returnKeys(self, cmd, inst):
        """ Generate all the keys describing our next file. """
        
        # IDKey = self.getIDKey(cmd, inst)
        pathKey = self.getPath(cmd, inst).getKey()
            
        #response = "%s; %s" % (IDKey, pathKey)
        
        cmd.respond(pathKey)
        
    def getPath(self, cmd, inst):
        """ Return an existing or new ExpPath for the given program+instrument. """
        
        id = self.getPathID(cmd, inst)
        path = self.knownExpPaths.get(id, None)
        if path == None:
            path = ExpPath.ExpPath(cmd.cmdrName, inst)

        self.knownExpPaths[id] = path

        return path
    
    def setPath(self, cmd, inst):
        """ Extract all the pathname parts from the command and configure (or create) the ExpPath. """

        #req, notMatched, opt, leftovers = cmd.coverArgs([],
        #                                                ['dir','name','seq','places'])
        req, notMatched, leftovers = cmd.match([('dir', cmd.qstr),
                                                ('name', cmd.qstr),
                                                ('seq', int),
                                                ('places', int)])
        path = self.getPath(cmd, inst)
        
        if req.has_key('dir'):
            path.setDir(req['dir'])
        if req.has_key('name'):
            path.setName(req['name'])
        if req.has_key('seq'):
            path.setNumber(req['seq'])
        if req.has_key('places'):
            path.setPlaces(req['places'])
            
        return path

    def seqFinished(self, seq):
        inst = seq.inst
        cmd = seq.cmd

        try:
            del self.openExposures[inst]
        except Exception, e:
            CPL.log("seqFinished", "exposure sequence for %s was not found (%s)." % (inst, self.openExposures.keys()))
            return
        
        cmd.finish('')

    def seqFailed(self, seq, reason):
        inst = seq.inst
        cmd = seq.cmd

        try:
            del self.openExposures[inst]
        except Exception, e:
            CPL.log("seqFailed", "exposure sequence for %s was not found." % (inst))
            return
        
        cmd.fail(reason)

    def normalizeInstname(self, name):
        """ Return the canonical name for a given instrument. """

        return name

# Start it all up.
#

def main(name, eHandler=None, debug=0, test=False):
    if eHandler == None:
        eHandler = ExposureActor(debug=1)
    eHandler.start()

    try:
        client.run(name=name, cmdQueue=eHandler.queue, background=False, debug=1, cmdTesting=test)
    except SystemExit, e:
        CPL.log('expose.main', 'got SystemExit')
        raise
    except:
        raise
    

def test():
    global mid
    mid = 1
    main('expose', test=True)

def tc(s):
    global mid
    
    client.cmd("APO CPL %d 0 %s" % (mid, s))
    mid += 1
    
if __name__ == "__main__":
    main('expose', debug=0)
