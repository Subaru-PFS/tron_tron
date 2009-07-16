__all__ = ['CommanderNub',
           'AuthCommanderNub',
           'StdinNub',
           'AuthStdinNub']

from NubAuth import NubAuth
import CoreNub
from Hub.Reply.ReplyTaster import ReplyTaster
import CPL

import g
import hub

class CommanderNub(CoreNub.CoreNub):
    """ Base class for ICC connections, where we accept commands from and send replies to the remote end.  """

    def __init__(self, poller, **argv):
        """

        KWArgs:
           isUser    - if True, we should be listed as a logged-in user.
           forceUser - override any automatically derived username.
        """

        CoreNub.CoreNub.__init__(self, poller, **argv)

        # Note which Replies we want to accept. The default
        # is to accept only responses to our own commands.
        #
        self.taster = ReplyTaster()
        self.taster.setFilter((), (self.name,), (self.name,))

        self.isUser = argv.get('isUser', False)

        if argv.has_key('forceUser'):
            program, user = argv.get('forceUser').split('.')
            self.setNames(program, user)

    def __str__(self):
        return "%s(id=%s, name=%s, type=%s)" % (self.__class__.__name__,
                                                self.ID, self.name, self.nubType)
        
    def setNames(self, programName, username):
        """ Set our program and usernames. """

        CPL.log('CommandeNub.setNames', 'setting name for %s to %s.%s' % (self, programName, username))
        
        newName = hub.validateCommanderNames(self, programName, username)
        self.setName(newName)

    def setName(self, newName):
        """ Change our username(s). """

        self.name = newName
        self.encoder.setName(self.name)
        self.decoder.setName(self.name)

    def copeWithInput(self, s):
        """ Incorporate new input: buffer it, then extract and operate each complete new command.

        Args:
           s   - the new, but still unbuffered, input.

        Returns:
           Nothing.

        """

        if self.debug > 2:
            CPL.log('Nub.copeWithInput', "CommanderNub %s read: %r" % (self.name, s))

        # Find and execute _every_ complete input.
        # The only time this function gets called is when new input comes in, so we
        # have no reliable mechanism for deferring input.
        #
        while 1:
            cmd, leftover = self.decoder.decode(self.inputBuffer, s)
            s = None
            self.inputBuffer = leftover
            if cmd == None:
                break

            if self.log:
                try:
                    txt = cmd['RawText']
                except:
                    txt = "UNKNOWN INPUT"
                self.log.log(txt, note='<')

            intercepted = False
            if hasattr(self, 'interceptCmd'):
                intercepted = self.interceptCmd(cmd)
                
            if not intercepted:
                hub.addCommand(cmd)

    def reply(self, r):

        # The authentication system want to be able to block all output until
        # the connection is established. Let an external agent "intercept" replies.
        #
        intercepted = False
        if hasattr(self, 'interceptReply'):
            intercepted = self.interceptReply(r)
        if intercepted:
            return

        # Most replies get sent to all interested commanders. But we allow
        # the possibility of only sending to the commander; in that case, 
        # the commander gets all replies and keys, but other commanders only get told
        # about command completion.
        # We do this by triaging out replies here, then optionally telling the encoder
        # whether to include keys.
        #
        if r.bcast or r.cmd.cmdrID == self.ID:
            er = self.encoder.encode(r, self)
            self.queueForOutput(er)
            if self.log:
                self.log.log(er, note='>')
        else:
            CPL.log("CommanderNub.reply", "not bcast; rID=%s selfID=%s" % (r.cmd.cmdrID, self.ID))
            if r.finishesCommand():
                er = self.encoder.encode(r, self, noKeys=True)
                self.queueForOutput(er)
                if self.log:
                    self.log.log(er, note='>')
        
    def tasteReply(self, r):
        if self.debug > 3:
            CPL.log('ActorNub.tasteReply', "%s tasting %s" % (self, r))

        if self.taster.taste(r):
            self.reply(r)

    def stopOutput(self):
        self.noOutput = True

    def startOutput(self):
        self.noOutput = False
        
class AuthCommanderNub(CommanderNub, NubAuth):
    """ A CommanderNub which enforces logins. """
    
    def __init__(self, poller, **argv):
        CommanderNub.__init__(self, poller, **argv)
        NubAuth.__init__(self, **argv)
        
class StdinNub(CommanderNub):
    def __init__(self, poller, in_f, out_f, **argv):
        CommanderNub.__init__(self, poller, **argv)

        self.mid = 1
        
        self.setInputFile(in_f)
        self.setOutputFile(out_f)
        
class AuthStdinNub(AuthCommanderNub):
    def __init__(self, poller, in_f, out_f, **argv):
        AuthCommanderNub.__init__(self, poller, **argv)

        self.mid = 1
        
        self.setInputFile(in_f)
        self.setOutputFile(out_f)
        
