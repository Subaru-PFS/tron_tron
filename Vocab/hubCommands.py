__all__ = ['hubCommands']

import time
import os

import CPL
from Hub.KV.KVDict import *
import Vocab.InternalCmd as InternalCmd
import g
import hub

class hubCommands(InternalCmd.InternalCmd):
    """ All the commands that the "hub" package provides.
    """
    
    def __init__(self, **argv):
        argv['safeCmds'] = '^\s*(actors|commanders|actorInfo|version|status)\s*$'
        InternalCmd.InternalCmd.__init__(self, 'hub', **argv)

        self.commands = { 'actors' : self.actors,
                          'commanders' : self.commanders,
                          'restart!' : self.reallyReallyRestart,
                          'startNubs' : self.startNubs,
                          'actorInfo' : self.actorInfo,
                          'commands' : self.commandInfo,
                          'setUsername' : self.setUsername,
                          'status' : self.status,
                          'loadWords' : self.loadWords,
                          'getKeys' : self.getKeys,
                          'version' : self.version,
                          }

    def version(self, cmd, finish=True):
        """ Return the hub's version number. """

        vString = "hubVersion=%s" % ("0.81")
        if finish:
            cmd.finish(vString)
        else:
            cmd.inform(vString)

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

    def startNubs(self, cmd):
        """ (re-)start a list of nubs. """

        nubs = cmd.argDict.keys()[1:]
        if len(nubs) == 0:
            nubs = ('tcc',
                    'dis', 'grim', 'echelle',
                    'disExpose', 'grimExpose', 'echelleExpose',
                    'TUI')

        ok = True
        for nub in nubs:
            try:
                hub.startNub(nub)
            except Exception, e:
                cmd.warn('hubTxt=%s' % (qstr("failed to start nub %s: %s" % (nub, e))))

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
                cmd.warn('hubTxt=%s' % (qstr("failed to query actor %s: %s" % (n, e))))

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
                cmd.warn('hubTxt=%s' % (qstr("failed to query actor %s: %s" % (n, e))))

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
            cmd.fail('hubTxt=%s' % (qstr(e)))
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
            cmd.fail('hubTxt="usage: getKeys srcName key1 [key2 ... keyN]"')
            return
        
        src = words[1]
        keys = words[2:]
        
        matched, unmatched = g.KVs.getValues(src, keys)
        CPL.log("hub.getKeys", "matched=%s unmatched=%s" % (matched, unmatched))
        for k, v in matched.iteritems():
            kvString = kvAsASCII(k, v)
            cmd.inform(kvString, src="hub.%s" % (src))
        if unmatched:
            cmd.warn("hubTxt=%s" % (qstr("unmatched %s keys: %s" % (src, ', '.join(unmatched)))))
        cmd.finish('')

    def reallyReallyRestart(self, cmd):
        """ Restart the entire MC. Which among other things kills us now. """

        cmd.warn('hubTxt=%s' % (qstr('Restarting the hub now... bye, bye, and please call back soon!')))

        # Give the poller a chance to flush out the warning.
        g.poller.callMeIn(hub.restart, 1.0)

        
           




