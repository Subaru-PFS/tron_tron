__all__ = ['hubCommands']

import sys

import CPL
from Hub.KV.KVDict import *
import Vocab.InternalCmd as InternalCmd
import g
import hub

class hubCommands(InternalCmd.InternalCmd):
    """ All the commands that the "hub" package provides.

    The user executes these from the command window:

    hub startNubs tspec
    hub status
    etc.
    """
    
    def __init__(self, **argv):
        argv['safeCmds'] = '^\s*(actors|commanders|actorInfo|version|status)\s*$'
        InternalCmd.InternalCmd.__init__(self, 'hub', **argv)

        self.commands = { 'actors' : self.actors,
                          'commanders' : self.commanders,
                          'restart!' : self.reallyReallyRestart,
                          'startNub' : self.startOneNub,
                          'startNubs' : self.startNubs,
                          'stopNubs' : self.stopNubs,
                          'actorInfo' : self.actorInfo,
                          'commands' : self.commandInfo,
                          'setUsername' : self.setUsername,
                          'status' : self.status,
                          'loadWords' : self.loadWords,
                          'getKeys' : self.getKeys,
                          'listen' : self.doListen,
                          'version' : self.version,
                          'ping' : self.status,
                          'relog' : self.relog,
                          }

    def version(self, cmd, finish=True):
        """ Return the hub's version number. """

        hub.getSetHubVersion()

        vString = 'version=%s' % (g.KVs.getKV('hub', 'version', default='Unknown'))
        if finish:
            cmd.finish(vString)
        else:
            cmd.inform(vString)

    def doListen(self, cmd):
        """ Change what replies get sent to us. """

        matched, unmatched, leftovers = cmd.match([('listen', None),
                                                   ('addActors', None),
                                                   ('setActors', None),
                                                   ('clearActors', None),
                                                   ('delActors', None)])

        cmdr = cmd.cmdr()
        if not cmdr:
            cmd.fail('debug=%s' % (CPL.qstr("cmdr=%s; cmd=%s" % (cmdr, cmd))))
            return
        CPL.log("doListen", "start: %s" % (cmdr.taster))
        CPL.log("doListen", "leftovers: %s" % (leftovers))
        
        if 'addActors' in matched:
            actors = list(leftovers.keys())
            CPL.log("doListen", "addActors: %s" % (actors))
            #cmd.inform('text="%s"' % (CPL.qstr("adding actors: %s" % (actors))))
            cmdr.taster.addToFilter(actors, [], actors)
            cmdr.taster.genKeys(cmd)
            cmd.finish()
        elif 'setActors' in matched:
            actors = list(leftovers.keys())
            CPL.log("doListen", "setActors: %s" % (actors))
            #cmd.inform('text="%s"' % (CPL.qstr("adding actors: %s" % (actors))))
            cmdr.taster.setFilter(actors, [], actors)
            cmdr.taster.genKeys(cmd)
            cmd.finish()
        elif 'delActors' in matched:
            actors = list(leftovers.keys())
            CPL.log("doListen", "delActors: %s" % (actors))
            #cmd.inform('text="%s"' % (CPL.qstr("removing actors: %s" % (actors))))
            cmdr.taster.removeFromFilter(actors, [], actors)
            cmdr.taster.genKeys(cmd)
            cmd.finish()
        elif 'clearActors' in matched:
            cmdr.taster.setFilter([], cmdr.taster.cmdrs, [])
            cmdr.taster.genKeys(cmd)
            cmd.finish()
        else:
            cmd.fail('text="unknown listen command"')
            
        CPL.log("doListen", "finish: %s" % (cmdr.taster))

    def actors(self, cmd, finish=True, verbose=False):
        """ Return a list of the currently connected actors. """

        g.actors.listSelf(cmd=cmd)
        if finish:
            cmd.finish('')
        
    def commanders(self, cmd, finish=True, verbose=False):
        """ Return a list of the currently connected commanders. """

        g.commanders.listSelf(cmd=cmd, verbose=False)
        if finish:
            cmd.finish('')
        
    def status(self, cmd, finish=True):
        CPL.cfg.flush()

        matched, unmatched, leftovers = cmd.match([('all', False)])
        verbose = 'all' in matched
        
        self.version(cmd, finish=False)
        self.actors(cmd, finish=False, verbose=verbose)
        self.commanders(cmd, finish=False, verbose=verbose)

        if finish:
            cmd.finish('')
            
    def setUsername(self, cmd):
        """ Change the username for the cmd's commander. """
        
        args = cmd.cmd.split()
        args = args[1:]

        if len(args) != 1:
            cmd.fail('cmdError="usage: setUsername newname"')
            return

        cmdr = cmd.cmdr()

        fullname = args[0]
        parts = fullname.split('.',1)
        if len(parts) == 2:
            name1 = parts[0]
            name2 = parts[1]
        elif len(parts) == 1:
            name1 = cmdr.name.split('.')[0]
            name2 = parts[0]
            
        hub.dropCommander(cmdr, doShutdown=False)
        cmdr.setNames(name1, name2)
        hub.addCommander(cmdr)
        cmdr.taster.genKeys(cmd)
        cmd.finish('')

    def stopNubs(self, cmd):
        """ stop a list of nubs. """

        nubs = list(cmd.argDict.keys())[1:]
        if len(nubs) == 0:
            cmd.fail('text="must specify one or more nubs to stop..."')
            return

        ok = True
        for nub in nubs:
            try:
                cmd.inform('text=%s' % (CPL.qstr("stopping nub %s" % (nub))))
                hub.stopNub(nub)
            except Exception as e:
                cmd.warn('text=%s' % (CPL.qstr("failed to stop nub %s: %s" % (nub, e))))

        cmd.finish('')

    def startNubs(self, cmd):
        """ (re-)start a list of nubs. """

        nubs = list(cmd.argDict.keys())[1:]
        if len(nubs) == 0:
            cmd.fail('text="must specify one or more nubs to start..."')
            return

        ok = True
        for nub in nubs:
            try:
                cmd.inform('text=%s' % (CPL.qstr("(re-)starting nub %s" % (nub))))
                hub.startNub(nub)
            except Exception as e:
                cmd.warn('text=%s' % (CPL.qstr("failed to start nub %s: %s" % (nub, e))))

        cmd.finish('')

    def startOneNub(self, cmd):
        """ (re-)start a nub, perhaps fully specified. 

        startNub nubName [hostname:port]

        """

        parts = list(cmd.argDict.keys())[1:]
        if len(parts) == 0:
            cmd.fail('text="must specify a nub to start..."')
            return

        nubName = parts[0]
        hostAndPort = parts[1] if len(parts) >= 2 else None
        if hostAndPort:
            hostname, port = hostAndPort.split(':')
        else:
            hostname, port = None, None

        try:
            port = int(port)
        except Exception as e:
            cmd.fail('text="nub port must be an integer, not %s"' % (port))
            return

        try:
            cmd.inform('text=%s' % (CPL.qstr("(re-)starting nub %s (%s:%s) " % (nubName, hostname, port))))
            hub.startNub(nubName, hostname=hostname, port=port)
        except Exception as e:
            cmd.warn('text=%s' % (CPL.qstr("failed to start nub %s: %s" % (nubName, e))))

        cmd.finish('')

    def actorInfo(self, cmd):
        """ Get gory status about a list of actor nubs. """

        # Query all actors if none are specified.
        names = list(cmd.argDict.keys())[1:]
        if len(names) == 0:
            names = list(g.actors.keys())
            
        for n in names:
            try:
                nub = g.actors[n]
                nub.statusCmd(cmd, doFinish=False)
            except Exception as e:
                cmd.warn('text=%s' % (CPL.qstr("failed to query actor %s: %s" % (n, e))))

        cmd.finish('')

    def commandInfo(self, cmd):
        """ Get gory status about a list of actor nubs. """

        # Query all actors if none are specified.
        names = list(cmd.argDict.keys())[1:]
        if len(names) == 0:
            names = list(g.actors.keys())
            
        for n in names:
            try:
                nub = g.actors[n]
                nub.listCommandsCmd(cmd, doFinish=False)
            except Exception as e:
                cmd.warn('text=%s' % (CPL.qstr("failed to query actor %s: %s" % (n, e))))

        cmd.finish('')

    def loadWords(self, cmd, finish=True):
        """ (re-)load an internal vocabulary word. """
        
        words = list(cmd.argDict.keys())[1:]

        if len(words) == 0:
            words = None

        CPL.log("hubCmd", "loadWords loading %s" % (words))
        try:
            hub.loadWords(words)
        except Exception as e:
            CPL.tback('hub.loadWords', e)
            cmd.fail('text=%s' % (CPL.qstr(e)))
            return
        
        if finish:
            cmd.finish()

    def getKeys(self, cmd):
        """ Return a bunch of keys for a given source. 

        Cmd args:
            src  - a key source name.
            keys - 1 or more key names.
        """
        
        words = cmd.cmd.split()
        if len(words) < 3:
            cmd.fail('text="usage: getKeys srcName key1 [key2 ... keyN]"')
            return
        
        src = words[1]
        keys = words[2:]
        
        matched, unmatched = g.KVs.getValues(src, keys)
        CPL.log("hub.getKeys", "matched=%s unmatched=%s" % (matched, unmatched))
        for k, v in matched.items():
            kvString = kvAsASCII(k, v)
            cmd.inform(kvString, src="hub.%s" % (src))
        if unmatched:
            cmd.warn("text=%s" % (CPL.qstr("unmatched %s keys: %s" % (src, ', '.join(unmatched)))))
        cmd.finish('')

    def reallyReallyRestart(self, cmd):
        """ Restart the entire MC. Which among other things kills us now. """

        cmd.warn('text=%s' % \
                 (CPL.qstr('Restarting the hub now... bye, bye, and please call back soon!')))

        # Give the poller a chance to flush out the warning.
        g.poller.callMeIn(hub.restart, 1.0)

    def relog(self, cmd):
        """ Change where stderr goes to. """
        
        args = cmd.cmd.split()
        args = args[1:]

        if len(args) != 1:
            cmd.fail('cmdError="usage: relog filename"')
            return

        filename = args[0]
        import os

        f = file(filename, "a", 1)
        os.dup2(f.fileno(), 1)
        os.dup2(f.fileno(), 2)
        sys.stdout = os.fdopen(1, "w", 1)
        sys.stderr = os.fdopen(2, "w", 1)
        f.close()

        cmd.finish('text="Jeebus, you done it now, whatever it was"')

