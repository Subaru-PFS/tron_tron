__all__ = ['ActorNub']

import re

from Hub.Command.Command import Command
from CoreNub import CoreNub

import CPL
import g

class ActorNub(CoreNub):
    """ Base class for ICC connections, where we send commands to and accept replies from the remote end.  """

    def __init__(self, poller, **argv):
        """ Create and connect an ActorNub. Takes the following optional arguments:
        grabCID    - a command to send, if we need to request a CID.
            Define our CID from the first response from the Actor
        initCmds   - list of strings
            Sent to the actor right after connection is established
        inform     - func(src, KVlist)
            If set, call when each command is dispatched and finished.
        replyCallback - func(cmd, reply)
            If set, called with eachreply line _instead of_ the cmd callback.
        logDir     - Log all I/O to the given directory
        """
        
        self.cid = None
        self.mid = 1
        
        CoreNub.__init__(self, poller, **argv)

        # Options:
        self.grabCID = argv.get('grabCID', False)
        self.initCmds = argv.get('initCmds', [])
        self.inform = argv.get('inform', None)
        self.replyCallback = argv.get('replyCallback', None)

        # Are we subject to permissions? If so, have we been given a name for 
        # permissions checking, or should we just use our name?
        #
        self.needsAuth = argv.get("needsAuth", False)
        if self.needsAuth == True:
            self.needsAuth = self.name
            
        safeCmds = argv.get('safeCmds', None)
        if safeCmds == None:
            self.safeCmds = None
        else:
            # Let this fail grotesquely.
            self.safeCmds = re.compile(safeCmds)
            CPL.log("ActorNub.init", "added safeCmds %s from %s" % (self.safeCmds, safeCmds))
            
        # All active commands that we are aware of, either because
        # we sent them, or because the actor replied to it.
        #
        self.liveCommands = {}
        
        # All active commands that we have sent to the actor.
        #
        self.ourCommands = {}

    def __str__(self):
        return "ActorNub(%s, cid=%s, mid=%s)" % (self.ID, self.cid, self.mid)
    
    def connected(self):
        """ Optionally send a list of commands after the connection has been established.

        This is complicated by .grabCID. If that exists, we want to sent a command just to
        force the actor to generate our CID. If we send the init comands before that is
        established, we will not recognize the replies as replies to our init commands.
        So if .grabCID is set and our .cid is not, send the .grabCID command, and let the .grabCID
        logic in copeWithInput() call us back when we are _really_ connected. Feh.
        
        """

        if self.grabCID != False and self.cid == None:
            if isinstance(self.grabCID, basestring):
                initCmds = [self.grabCID]
            else:
                initCmds = []
            doRegister = False
        else:
            initCmds = self.initCmds
            doRegister = True
        
        CPL.log("ActorNub.connected", "sending initCmds to %s (cid=%s)" % (self.ID, self.cid))
        for c in initCmds:
            CPL.log("ActorNub.connected", "sending initCmd %s" % (c))
            self.sendCommand(Command('.hub', '0',
                                     g.hubMIDs.gimme(),
                                     self.name, c),
                             doRegister=doRegister)
            
    def sendCommand(self, c, doRegister=True):
        """ Main entry point for sending a command.

        Args:
          c   - a Command instance.

        Optional args:
          doRegister - if True (the default), keep track of replies.
        """
        
        # Check whether we can encode the command first:
        #
        self.__registerOurCmd(c, doRegister=doRegister)
            
        ec = self.encoder.encode(c)

        c.reportQueued()
        self.queueForOutput(ec)
        if self.log:
            self.log.log(ec, note='>')
            
    def copeWithInput(self, s):
        """ Incorporate new input: buffer it, then extract and operate on each complete reply.

        Args:
           s   - the new, but still unbuffered, input.
        """

        if self.debug > 6:
            CPL.log('Nub.copeWithInput', "ActorNub %s read: %s" % (self.name, s))

        # Find and execute _every_ complete input.
        # The only time this function gets called is when new input comes in, so we
        # have no reliable mechanism for deferring input. If we need to, we could
        # adapt the PollHandler to query for unconsumed input. Hmm, maybe not.
        #
        while 1:
            reply, leftover = self.decoder.decode(self.inputBuffer, s)
            s = None
            self.inputBuffer = leftover
            if reply == None:
                break

            if self.log:
                try:
                    txt = reply['RawText']
                except:
                    txt = "UNKNOWN INPUT"
                self.log.log(txt, note='<')
            
            # Optionally try to fetch our CID by looking at the first reply.
            # The actor had better reply to our connection...
            #
            if self.cid == None and self.grabCID != False:
                CPL.log("Nub.copeWithInput", "setting %s cid=%s" % (self.name, reply['cid']))
                self.cid = reply['cid']
                self.connected()
                
            cmd = self.getCmdForReply(reply)
            cmd.addReply(reply)
        
    def keyForCommand(self, cmd):
        """ Generate an immutable unique key for this command.

        This should perhaps go into the encoder?
        """

        return (str(cmd.actorCid), str(cmd.actorMid))
    
    def keyForReply(self, reply):
        """ Extract the key for this reply. Must match what .keyForCommand() is doing.

        This should perhaps go into the decoder?
        """

        return (str(reply['cid']), str(reply['mid']))
    
    def __registerCmd(self, cmd, ours):
        """ """
        
        key = self.keyForCommand(cmd)
        
        if self.debug > 0:
            CPL.log("Nub", "registering key(ours=%s)=%s for %s" % (key, ours, cmd))
        if ours and self.liveCommands.has_key(key):
            raise RuntimeError("Duplicate command key for %s: %s" % (self, key))

        self.liveCommands[key] = cmd
        if ours:
            self.ourCommands[key] = cmd
        
    def __registerOurCmd(self, cmd, doRegister):
        """ We keep a registry of active commands, both ones that we sent and ones that we have detected.
        """
        
        cid = self.cid
        if cid == None:
            cid = 0
        cmd.connectToActor(cid, self.mid)
        self.mid += 1

        if doRegister:
            self.__registerCmd(cmd, ours=True)
        
    def __registerExternalCmd(self, cid, mid):
        """ Whenever we see input from a command that we did not send, create a Command to match. """

        key = (str(cid), str(mid))
        cmd = self.liveCommands.get(key)
        if not cmd:
            fullName = ".%s" % (self.name)
            cmd = Command(fullName, ".%s" % (self.name), mid, self.name, None,
                          actorCid=cid, actorMid=mid,
                          bcastCmdInfo=False)
            self.__registerCmd(cmd, ours=False)

        return cmd
    
    def getCmdForReply(self, reply):
        """ Look for a command that matches the reply. Create one if none exists. """
        
        key = self.keyForReply(reply)
        
        cmd = self.liveCommands.get(key, None)
        if cmd == None and self.replyCallback == None:
            cmd = self.__registerExternalCmd(reply['cid'], reply['mid'])
        
        if self.flagFinishesCommand(reply['flag']):
            if cmd:
                del self.liveCommands[key]
            
            try:
                del self.ourCommands[key]
            except:
                pass
            
        return cmd
    
    def tasteReply(self, r):
        assert False, "A reply was sent to an Actor(%s): %s" % (self, r)

    def statusCmd(self, cmd, doFinish=True):
        """ Send sundry status information keywords.
        """

        CoreNub.statusCmd(self, cmd, doFinish=False)
        self.listCommandsCmd(cmd, doFinish=False)

        if doFinish:
            cmd.finish()

    def listCommandsCmd(self, cmd, doFinish=True):
        """ Send command keywords.
        """

        cmd.inform('actorCmds=%s,%d,%d' % \
                   (CPL.qstr(self.name), len(self.liveCommands), len(self.ourCommands)))

        for id, ourCmd in self.ourCommands.iteritems():
            cmd.inform('actorCmd=%s,%s,%s' % \
                   (CPL.qstr(self.name), CPL.qstr(id), CPL.qstr(ourCmd)))
            

