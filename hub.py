#!/usr/bin/env python

"""
   The core of the hub.
   The hub basically:
      - maintains a keyword-value ("KV") dictionary,
      - accepts commands from Commanders and passes them onto Actors,
      - accepts and generates KV responses, and passes them on to interested parties.

   We handle the fact that we can get (or generate) responses to commands that that we
   did not send by creating Commands for all responses.

   c = Command()
      cmdrCid, cmdrMid
      tgt, cmd
      [xid]
      
      actorCid, actorMid

   r = Reply(cmd=cmd
"""

import imp
import os
import re
import signal
import sys
import time
import collections

import CPL
from Misc.cdict import cdict

import IO
import Hub.KV.KVDict
import Hub.Command.Command
import Auth
import g

def init(configName=''):
    g.home = sys.path[0]
    if g.home == None or g.home == '':
        g.home = os.getcwd()

    g.rootDir = os.getcwd()

    # Bootstrap the whole configuration system
    configPath = os.environ.get('CONFIG_DIR',
                                os.path.join(os.environ['TRON_DIR'], 'config', configName))
    CPL.cfg.init(path=configPath)
    os.environ['CONFIG_DIR'] = configPath
    
    g.logDir = CPL.cfg.get('hub', 'logDir')
    CPL.setLogdir(g.logDir)
    CPL.setID('hub')
    CPL.log('hub.init', 'logger started...')

    #   - a globally unique ID generator for Commands.
    g.xids = CPL.ID()
    g.nubIDs = CPL.ID()
    g.hubMIDs = CPL.ID()
    
    # The Hub is basically:
    #   All of these are in the global namespace "g".
    #
    #   - A dictionary of KVs
    g.KVs = Hub.KV.KVDict.KVDict(debug=3)

    g.commanders = cdict()
    g.actors = cdict()

    g.hubcmd = None
    g.hubcmd = Hub.Command.Command('.hub', '0', 0, 'hub', None, actorCid=0, actorMid=0, neverEnd=True)

    #   - An authorization manager
    permsCmd = Hub.Command.Command('.perms', '0', 0, 'perms', None, actorCid=0, actorMid=0, neverEnd=True)
    g.perms = Auth.Auth(permsCmd, debug=9)
    
    #   - A dictionary of Commander Nubs, indexed by unique ID.
    g.commanders = CmdrDict('Commanders')
    # g.listeners = g.commanders

    #   - A dictionary of Actor Nubs, indexed by name
    g.actors = NubDict('Actors')
    g.vocabulary = cdict()

    #   - dictionary of PollAcceptors, waiting for for new connections.
    g.acceptors = cdict()

    #   - dictionary of active commands, indexed by XID.
    g.pendingCommands = {}

    #   - A PollHandler
    g.poller = IO.PollHandler(debug=1)

    CPL.log('hub.init', 'loading internal vocabulary...')
    loadWords(None)
    
    CPL.log('hub.init', 'loading keys...')
    loadKeys()

    # atexit.register(shutdown)
    signal.signal(signal.SIGHUP, handleSIGHUP)
    signal.signal(signal.SIGTERM, handleSIGTERM)

    #   - A security manager

def handleSIGHUP(signal, frame):
    restart()
    
def handleSIGTERM(signal, frame):
    shutdown()

def getSetHubVersion():
    """ Put the uncached svn version info into the hub.version keyword. """

    version = "need_to_read_git_version"
    g.KVs.setKV('hub', 'version', version, None)

def loadKeys():
    rootDir = CPL.cfg.get('hub', 'httpRoot')
    host = CPL.cfg.get('hub', 'httpHost')

    g.KVs.setKV('hub', 'httpRoot', [host, rootDir], None)

    getSetHubVersion()
    
def loadWords(words=None):
    if words == None:
        words = CPL.cfg.get('hub', 'vocabulary')

    for w in words:
        _loadWords([w])

def _loadWords(wordlist):
    """ (Re-)load a list of Vocabulary words, overwriting any existing info. 
    """

    # First, (re-)load the entire Vocabulary module. Let that fail to the top
    # level.
    #
    CPL.log('hub.loadVocab', 'trying to (re-)load Vocab module')
    fp, pathname, description = imp.find_module('Vocab')
    vocab_mod = imp.load_module('Vocab', fp, pathname, description)
    if fp:
        fp.close()
    CPL.log('hub.loadVocab', 'Vocab module: %s' % (dir(vocab_mod)))
     
    for w in wordlist:
        # Now try to load the module itself.
        #
        modName = w
        if w == 'hub':
            modName = 'hubCommands'
        try:
            CPL.log('hub.loadVocab', 'trying to (re-)load vocabulary word %s' % (w,))
            fp, pathname, description = imp.find_module(modName, vocab_mod.__path__)
            mod = imp.load_module(modName, fp, pathname, description)
        except ImportError, e:
            raise Exception('Import of %s failed: %s' % (modName, e))

        if fp:
            fp.close()

        loadCmd = 'cmdSet = mod.%s()' % (modName)
        CPL.log('hub.loadWords', 'loading vocabulary word %s with %s...' % (w, loadCmd))

        try:
            exec(loadCmd)
            try:
                dropActor(cmdSet)
            except:
                pass
            g.vocabulary[w] = cmdSet
        except Exception, e:
            raise Exception("Failed to load word %s: %s" % (w, e))

        addActor(cmdSet)
        
        CPL.log('hub.loadWords', 'vocabulary: %s' % (g.vocabulary))
        
def shutdown():
    CPL.log('hub.shutdown', 'shutting down......................................')
    try:
        _shutdown()
    except:
        pass
    sys.exit(0)

def restart():
    CPL.log('hub.restart', 'restarting......................................')
    try:
        _shutdown()
    except:
        pass

    CPL.log('hub.restart', 'for real......................................')
    time.sleep(1)
    os.execlp("tron", "tron", "restart")
    
def _shutdown():
    sys.stderr.write("final cleanup; deleting hub pieces...\n")
    
    sys.stderr.write("       deleting acceptors...\n")
    for aname, acceptor in g.acceptors.items():
        try:
            acceptor.shutdown(notifyHub=False)
        except:
            pass
            
    sys.stderr.write("       deleting commanders...\n")
    for cname, cmdr in g.commanders.items():
        try:
            cmdr.shutdown(notifyHub=False)
        except:
            pass
            
    sys.stderr.write("       deleting actors...\n")
    for aname, actor in g.actors.items():
        try:
            actor.shutdown(notifyHub=False)
        except:
            pass
    
def run():
    """ Listens for and handles I/O on all devices.
    """
    while 1:
        try:
            CPL.log("hub.run", "actors id=%r" % (id(g.actors)))
            g.poller.run()
        except (SystemExit, KeyboardInterrupt):
            CPL.log('Hub.run', 'Normal exit."')
            raise
        
        except Exception, e:
            CPL.tback('Hub.run', e)

class NubDict(collections.OrderedDict):
    """ Arrange for access to a dictionary to be annotated. """
    def __init__(self, name):
        collections.OrderedDict.__init__(self)
        self.name = name
        self.listSelf()
        
    def __setitem__(self, k, v):
        collections.OrderedDict.__setitem__(self, k, v)

        self.listSelf()

    def __delitem__(self, k):
        # k.shutdown(notifyHub=False)
        collections.OrderedDict.__delitem__(self, k)

        self.listSelf()

    def listSelf(self, cmd=None):
        names = []
        for n in self.itervalues():
            names.append(CPL.qstr(n.name))

        if not cmd:
            cmd = g.hubcmd

        cmd.inform("%s=%s" % (self.name, ','.join(names)))

class CmdrDict(NubDict):
    """ Like NubDict, but generate a 'users' keyword, depending on
        the state of the nub's isUser attribute.

        Also, list the taster attributes
    """
    
    def listSelf(self, cmd=None, verbose=False):
        if not cmd:
            cmd = g.hubcmd
        names = []
        userNames = []
        for n in self.itervalues():
            names.append(CPL.qstr(n.name))
            if n.isUser:
                userNames.append(CPL.qstr(n.name))
            CPL.log('listCommanders', 'n=%s has info=%s' % (n, n.userInfo))
            if n.userInfo:
                cmd.inform(n.userInfo)
            if verbose:
                n.taster.genKeys(cmd, n.name)
        cmd.inform("%s=%s" % (self.name, ','.join(names)))
        cmd.inform("users=%s" % (','.join(userNames)))

    
def addNubToDict(nub, nubDict):
    """ Add a new nub to the given dict. The nub's ID must not be the same as for any existing nub. """

    existingNub = findNubInDict(nub.ID, nubDict)
    if existingNub != None:
        CPL.log("Hub.nubs", "nub %s already exists; not overwriting" % (nub.ID))
        return
    
    nubDict[nub.ID] = nub
    CPL.log('Hub.nubs', 'added nub %s to %s' % (nub, nubDict))
        
    
def dropNubFromDict(nub, nubDict, doShutdown=True):
    """ Close an existing nub. The nub must, of course, be in the given nub dict. """

    CPL.log('Hub.nubs', 'dropping nub=%s shutdown=%s' % (nub, doShutdown))
    if doShutdown:
        nub.shutdown(notifyHub=False)

    nub = findNubInDict(nub.ID, nubDict)
    if nub == None:
        CPL.log('Hub.nubs', 'nub %s is not registered; not dropping it' % (nub.ID))
        return
    
    del nubDict[nub.ID]

def findNubInDict(id, nubDict):
    """ Return the named nub, or None if it does not exist. """
    
    return nubDict.get(id, None)
    
    
def addActor(nub):
    addNubToDict(nub, g.actors)
    g.KVs.addSource(nub.name)
    if nub.needsAuth:
        g.perms.addActors([nub.needsAuth])
    
def dropActor(nub):
    # g.perms.dropActors([nub.name])
    g.KVs.clearSource(nub.name)
    dropNubFromDict(nub, g.actors)

def findActor(id): return findNubInDict(id, g.actors)

def addCommander(nub):
    CPL.log("hub.addCommander", "adding %s" % (nub.name))
    addNubToDict(nub, g.commanders)
    
def dropCommander(nub, doShutdown=True):
    CPL.log("hub.dropCommander", "dropping %s" % (nub.name))
    dropNubFromDict(nub, g.commanders, doShutdown=doShutdown)
    
def findCommander(id): return findNubInDict(id, g.commanders)

def addAcceptor(nub): addNubToDict(nub, g.acceptors)
def dropAcceptor(nub): dropNubFromDict(nub, g.acceptors)
def findAcceptor(id): return findNubInDict(id, g.acceptors)

def findNub(nub):
    """ Find whether a nub exists in any of the nub dictionaries. """
    
    for d in (g.actors, g.commanders, g.acceptors):
        if nub in d:
            return d[nub]
    return None

def dropNub(nub):
    """ Drop a Nub, regardless of its type. """

    if nub.ID in g.actors:
        dropActor(nub)
    elif nub.ID in g.commanders:
        dropCommander(nub)
    elif nub.ID in g.acceptors:
        dropAcceptor(nub)
    else:
        CPL.log("hub.dropNub",
                "nub %s (%s) is neither in g.actors (%s) or g.commanders (%s)" % \
                (nub.ID, nub, g.actors, g.commanders))

def listActors(match):
    """ """

    actors = g.actors.keys()
    actors.sort()
    
    return actors

def validateCommanderNames(nub, programName, username):
    """ Transform a proposed CommanderNub name into a unique CommanderNub name.

    A Commander name must consist of a program name and a username separated by a period.
    Basically, take the proposed name and add _%d until there is no collision.
    """

    # Severely normalize the username
    #
    programName = re.sub('[^a-zA-Z0-9_]+', '_', programName)
    username = re.sub('[^a-zA-Z0-9_]+', '_', username)

    if re.match('[a-zA-Z_]', username) == None:
        username = '_' + username
    if re.match('[a-zA-Z_]', programName) == None:
        programName = '_' + programName

    fullName = "%s.%s" % (programName, username)

    n = 2
    proposedName = fullName
    ok = False
    while not ok:
        ok = True
        for c in g.commanders.itervalues():
            if c.name == proposedName:
                ok = False
                break
        if not ok:
            proposedName = "%s_%d" % (fullName, n)
            n += 1

    return proposedName
    
def listKeys(match, **argv):
    cmd = argv.get('cmd')
    
def getActor(cmd):
    """ Find either an actor or vocabulary word matching the given command.
    """

    actorName = cmd.actorName

    CPL.log("hub.getActor", "looking for actor %s" % (actorName))
    tgt = g.actors.get(actorName, None)

    if tgt == None:
        CPL.log("hub.getActor", "looking for vocabulary word %s" % (actorName))
        tgt = g.vocabulary.get(actorName, None)
        
    CPL.log("hub.getActor", "target = %s" % (tgt))
    return tgt

def addCommand(cmd):
    """ Add a new command, and arrange for it to be executed by the appropriate target.

    Need to add:
        Automatically start an Actor if it is not running. Do this by:
          - check for starteable Nub - just call startNub in a catch.
          - send (i.e. queue) the command. We need to add the logic for the Actor's
        queue to be flushed when the connection has been established.

          - Provide some throttling to avoid idiocy when, say, the tcc password is changed.
    """

    CPL.log("hub.addCommand", "new cmd=%s" % (cmd))
    
    if cmd.actorName == 'dbg':
        runCmd(cmd)
        return

    actor = getActor(cmd)

    if actor == None:
        cmd.fail('NoTarget=%s' % \
                 CPL.qstr("the target named %s is not connected" % (cmd.actorName)),
                 src='hub')
        return

    # Enforce permissions if the actor requires them.
    ok = g.perms.checkAccess(cmd.cmdrCid, actor, cmd)
    if not ok:
        cmd.fail('NoPermission=%s' % \
                 CPL.qstr("you do not have permission to command %s" % \
                          (actor.needsAuth)),
                 src='hub')
        return
    
    actor.sendCommand(cmd)

def runCmd(c):
    cmd = c.cmd.strip()
    CPL.log("hub.runCmd", "cmd = %r" % (cmd))
    if cmd == "":
        c.finish("Eval=%s" % (CPL.qstr("")),
                 src='hub')
        return
    
    try:
        ret = eval(cmd)
    except Exception, e:
        c.fail('EvalError=%s' % CPL.qstr(e),
               src='hub')
        raise
    
    c.finish("Eval=%s" % (CPL.qstr(ret)), src='hub')
    CPL.log("hub.runCmd", "ret = %r" % (ret))


def listenTo(**argv):
    """ Arrange for the given events to be accepted. """
    pass

def loadVocab(**argv):
    """ Load the entire Vocabulary, overwriting any existing info. """

    # First, (re-)load the entire Nubs module. Let that fail to the top
    # level.
    #
    fp, pathname, description = imp.find_module('Vocab')
    vocab_mod = imp.load_module('Vocab', fp, pathname, description)
    if fp:
        fp.close()
     
    # Now try to load the module itself.
    #
    try:
        CPL.log('hub.loadVocab', 'trying to (re-)load vocabulary')
        fp, pathname, description = imp.find_module(name, vocab_mod.__path__)
    except:
        raise

    try:
        mod = imp.load_module(name, fp, pathname, description)
    finally:
        # Since we may exit via an exception, close fp explicitly.
        if fp:
            fp.close()

    # And call the start() function.
    #
    CPL.log('hub.startAConnection', 'starting Nub %s...' % (name))
    mod.start(g.poller)

def stopNub(id):
    """  """

    n = findNub(id)
    if n:
        n.shutdown(notifyHub=False)
        dropNub(n)

def forceReload(name, all=True):
    """ Do whatever we can to force a given module/package to be reloaded.
    
    """

    mod = None
    partName = name
    if all:
        # Optionally (re-)load all the containing modules. Let that fail to the top
        # level.
        #
        start = 0
        while 1:
            end = name.find('.', start)
            if end == -1:
                partName = name[start:]
                break
            partName = name[start:end]
            start = end+1

            CPL.log('hub.forceReload', 'trying to (re-)load module %s in %s' % (partName, mod))
            if mod == None:
                fp, pathname, description = imp.find_module(partName)
            else:
                fp, pathname, description = imp.find_module(partName, mod.__path__)

            try:
                mod = imp.load_module(partName, fp, pathname, description)
            finally:
                if fp:
                    fp.close()
     
    # Now try to load the module itself.
    #
    try:
        CPL.log('hub.forceReload', 'trying to (re-)load final %s in %s' % (partName, mod))
        if mod == None:
            fp, pathname, description = imp.find_module(partName)
        else:
            fp, pathname, description = imp.find_module(partName, mod.__path__)
    except:
        raise

    try:
        mod = imp.load_module(name, fp, pathname, description)
    finally:
        # Since we may exit via an exception, close fp explicitly.
        if fp:
            fp.close()

    return mod

def stopNub(name):
    n = findActor(name)
    if n:
        dropActor(n)

def startNub(name):
    """ Launch a single Nub. 

    (Re-)Loads a module named 'name' from the Nubs folder and calls the start function.
    """

    CPL.log('hub.startNub', 'trying to start %s' % (name))

    # First, (re-)load the entire Nubs module. Let that fail to the top
    # level.
    #
    fp, pathname, description = imp.find_module('Nubs')
    nubs_mod = imp.load_module('Nubs', fp, pathname, description)
    if fp:
        fp.close()
     
    # Now try to load the module itself.
    #
    try:
        CPL.log('hub.startNub', 'trying to (re-)load Nub %s' % (name))
        fp, pathname, description = imp.find_module(name, nubs_mod.__path__)
    except:
        raise

    try:
        mod = imp.load_module(name, fp, pathname, description)
    finally:
        # Since we may exit via an exception, close fp explicitly.
        if fp:
            fp.close()

    # And call the start() function.
    #
    CPL.log('hub.startNub', 'starting Nub %s...' % (name))
    mod.start(g.poller)
