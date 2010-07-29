__all__ = ['hubCommands']

import sys
import time
import os

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
                                                   ('delActors', None)])

        cmdr = cmd.cmdr()
        if not cmdr:
            cmd.fail('debug=%s' % (CPL.qstr("cmdr=%s; cmd=%s" % (cmdr, cmd))))
            return
        CPL.log("doListen", "start: %s" % (cmdr.taster))
        CPL.log("doListen", "leftovers: %s" % (leftovers))
        
        if 'addActors' in matched:
            actors = leftovers.keys()
            CPL.log("doListen", "addActors: %s" % (actors))
            #cmd.inform('text="%s"' % (CPL.qstr("adding actors: %s" % (actors))))
            cmdr.taster.addToFilter(actors, [], actors)
            cmd.finish()
        elif 'delActors' in matched:
            actors = leftovers.keys()
            CPL.log("doListen", "delActors: %s" % (actors))
            #cmd.inform('text="%s"' % (CPL.qstr("removing actors: %s" % (actors))))
            cmdr.taster.removeFromFilter(actors, [], actors)
            cmd.finish()
        else:
            cmd.fail('text="unknown listen command"')
            
        CPL.log("doListen", "finish: %s" % (cmdr.taster))

    def actors(self, cmd, finish=True):
        """ Return a list of the currently connected actors. """

        g.actors.listSelf(cmd=cmd)
        if finish:
            cmd.finish('')
        
    def commanders(self, cmd, finish=True):
        """ Return a list of the currently connected commanders. """

        g.commanders.listSelf(cmd=cmd)
        if finish:
            cmd.finish('')
        
    def status(self, cmd, finish=True):
        CPL.cfg.flush()

        self.version(cmd, finish=False)
        self.actors(cmd, finish=False)
        self.commanders(cmd, finish=False)

        if finish:
            cmd.finish('')
            
    def setUsername(self, cmd):
        """ Change the username for the cmd's commander. """
        
        args = cmd.cmd.split()
        args = args[1:]

        if len(args) != 1:
            cmd.fail('cmdError="usage: setUsername newname"')
            return

        username = args[0]
        cmdr = cmd.cmdr()
        cmdr.setName(username)
        cmd.finish('')

    def stopNubs(self, cmd):
        """ stop a list of nubs. """

        nubs = cmd.argDict.keys()[1:]
        if len(nubs) == 0:
            cmd.fail('text="must specify one or more nubs to stop..."')
            return

        ok = True
        for nub in nubs:
            try:
                cmd.inform('text=%s' % (CPL.qstr("stopping nub %s" % (nub))))
                hub.stopNub(nub)
            except Exception, e:
                cmd.warn('text=%s' % (CPL.qstr("failed to stop nub %s: %s" % (nub, e))))

        cmd.finish('')

    def startNubs(self, cmd):
        """ (re-)start a list of nubs. """

        nubs = cmd.argDict.keys()[1:]
        if len(nubs) == 0:
            cmd.fail('text="must specify one or more nubs to start..."')
            return

        ok = True
        for nub in nubs:
            try:
                cmd.inform('text=%s' % (CPL.qstr("(re-)starting nub %s" % (nub))))
                hub.startNub(nub)
            except Exception, e:
                cmd.warn('text=%s' % (CPL.qstr("failed to start nub %s: %s" % (nub, e))))

        cmd.finish('')

    def actorInfo(self, cmd):
        """ Get gory status about a list of actor nubs. """

        # Query all actors if none are specified.
        names = cmd.argDict.keys()[1:]
        if len(names) == 0:
            names = g.actors.keys()
            
        for n in names:
            try:
                nub = g.actors[n]
                nub.statusCmd(cmd, doFinish=False)
            except Exception, e:
                cmd.warn('text=%s' % (CPL.qstr("failed to query actor %s: %s" % (n, e))))

        cmd.finish('')

    def commandInfo(self, cmd):
        """ Get gory status about a list of actor nubs. """

        # Query all actors if none are specified.
        names = cmd.argDict.keys()[1:]
        if len(names) == 0:
            names = g.actors.keys()
            
        for n in names:
            try:
                nub = g.actors[n]
                nub.listCommandsCmd(cmd, doFinish=False)
            except Exception, e:
                cmd.warn('text=%s' % (CPL.qstr("failed to query actor %s: %s" % (n, e))))

        cmd.finish('')

    def loadWords(self, cmd, finish=True):
        """ (re-)load an internal vocabulary word. """
        
        words = cmd.argDict.keys()[1:]

        if len(words) == 0:
            words = None

        CPL.log("hubCmd", "loadWords loading %s" % (words))
        try:
            hub.loadWords(words)
        except Exception, e:
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
        for k, v in matched.iteritems():
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

