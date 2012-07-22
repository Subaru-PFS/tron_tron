__all__ = ['Command']
           
import re 
import time

import collections
import CPL
from Hub.Reply.Reply import Reply
import Parsing
import g

class Command(CPL.Object):
    """ Maintain everything required to shepherd a command through the hub.

    Basically, we need to track the commander's MID and CID, the internal XID,
    the target's ID, and the MID we use to call the target.

    The Command is created with the commander's info, and is populated with other
    things later.

    Where did the command come from?
      cmdrCID - the Commander's name, which is:
                     programName.username[.trail]
                Any real Commander will have a real programName and username.
                Synthetic Commands can be created from Replys to commands which
                we did not send. Those are assigned to .actorName
      cmdrMID - the Commander's MID
    """

    def __init__(self, cmdrID, cid, mid, tgt, cmd, **argv):
        """
        On commands from a Commander:
            - cmdrCID, cmdrMID are what the Commander sent
            - cmdrID is the programname.username (cmdr.fullname())
        On commands from an Actor (synthetic Commands):
            - cmdrCID, cmdrMID are what the Actor used.
            - cmdrID is .actorname.
        """

        CPL.Object.__init__(self, **argv)

        # An internally unique identifier for the command. We could use cmdr + the Commander's
        # CID + MID, but that would leave us trusting the Cmdr.
        self.xid = g.xids.gimme()
        self.ctime = time.time()

        # The source of the command.
        self.cmdrID = cmdrID
        try:
            cmdr = g.commanders[cmdrID]
            self.cmdrName = cmdr.name
        except:
            self.cmdrName = cmdrID
            CPL.log("Command", "no commander %s" % (cmdrID))
                    
        # How the caller wants the command identified.
        if cid == None:
            cid = ".%s" % (self.cmdrID)
        self.cmdrCid = cid
        self.cmdrMid = mid

        # Who will operate on the command, and the command itself.
        self.actorName = tgt
        self.cmd = cmd

        # The identification the the hub gives to the actor.
        self.actorCid = argv.get('actorCid', None)
        self.actorMid = argv.get('actorMid', 0)
        
        # Some Commands are essentially permanent.
        self.neverEnd = argv.get('neverEnd', False)
        
        # Register ourselves in a convenient place.
        # g.pendingCommands[self.xid] = self
        
        if self.cmdrCid == None:
            cid_s = "None"
        else:
            cid_s = self.cmdrCid

        if self.cmd == None:
            cmd_s = ""
        else:
            cmd_s = self.cmd

        self.argDict = None
        
        # We need to put this silly test here, 'cuz the hub creates g.hubcmd at startup,
        # and g.hubcmd does not yet exist when it is being created...
        #
        self.bcastCmdInfo = argv.get('bcastCmdInfo', True)
        
        if g.hubcmd != None and self.bcastCmdInfo:
            g.hubcmd.diag("CmdIn=%s,%s,%s" %
                          (CPL.qstr(self.cmdrCid), 
                           CPL.qstr(self.actorName),
                           CPL.qstr(self.cmd)),
                          src='cmds')
            
    def __str__(self):
        return "Command(xid=%s, cmdr=%s, cmdrCid=%s, cmdrMid=%s, actor=%s, cmd=%s)" % \
               (self.xid, self.cmdrName, self.cmdrCid, self.cmdrMid, self.actorName,
                CPL.qstr(self.cmd))


    def _names(self):
        """ Return our program and username. """

        return self.cmdrName.split('.', 1)
    
    def username(self):
        """ Return the username that invoked us. """

        return self._names()[1]
    
    def program(self):
        """ Return the program that we belong to. """

        return self._names()[0]

    def reportQueued(self):
        if g.hubcmd != None and self.bcastCmdInfo:
            g.hubcmd.diag(("CmdQueued=%d,%0.2f,%s,%s,%s,%s,%s" %
                           (self.xid, self.ctime,
                            CPL.qstr(self.cmdrCid), self.cmdrMid,
                            CPL.qstr(self.actorName), self.actorMid,
                            CPL.qstr(self.cmd))),
                          src='cmds')

    def connectToActor(self, cid, mid):
        """ Note the parts of the command we can only figure out when connected to the target. """
        
        self.actorCid = cid
        self.actorMid = mid
        
    """
       The command syntax that we accept is:
           cmd        := cmdword args
           cmdWord    := [a-zA-Z_]\S*
           args       := 
                         | arg
                         | args arg
           arg        := key | keyval
           key        := [a-zA-Z_][a-zA-Z0-9_]*
           keyval     := key\s*=\s*val
           val        := vpart
                         | val,vpart
           vpart      := string
                         | not-string
    """
    
    v_re = re.compile(r"""
        ^\s*                # Ignore leading space 
        (?P<val>[^ \t,]+)   # Match the (sub-)value 
        \s*                 # Ignore spaces 
        (?P<rest>.*)        # Match eveything after the delimiter""",
                      re.IGNORECASE|re.VERBOSE)

    def cmdr(self):
        """ Return our commander. """

        for c in g.commanders.values():
            CPL.log("Command.cmdr()" , "checking %s in %s" % (self.cmdrName, c))
            if self.cmdrName == c.name:
                CPL.log("Command.cmdr()" , "matched %s in %s" % (self.cmdrName, c))
                return c

        CPL.log("Command.cmdr()" , "no cmdr %s in %s" % (self.cmdrName, g.commanders))
        return None
        
        
    def eatAVee(self, s):
        # Match a non-string value -- a value ended by:
        #  - whitespace,
        #  - a comma,
        #  - EOL
        #
        # Returns:
        #  - the matched value,
        #  - the rest of the input, with leading spaces removed.
        #
        # If by some misunderstanding there is no match, return the rest
        # of the line as the value. This avoids infinite loops.
        #
        
        # CPL.log('eatAVee', 'called with %s' % (s))
        
        matches = self.v_re.match(s)
        if matches:
            return matches.groupdict()
        else:
            g.hubcmd.inform('ParseError=%s' % (CPL.qstr("Consuming all trailing text '%s'" % (s))),
                            src='hub')
        return {'val':CPL.qstr(s), 'rest':''}

    def eatAString(self, s):
        # Match a quoting-escaped string.
        #
        # Returns:
        #  - the matched string, or the rest of the line,
        #  - the quoting level at the end of the string -- 0 if we closed
        #       the string, 1 if not.
        #  - the rest of the input, with leading spaces removed.
        #
    
        # Basically, scan a string while counting backslashes. If we come to a
        # quote preceded by an even number of backslashes (trivially 0), consider
        # the string matched.
        #
    
        # CPL.log('eatAString', 'called with %s' % (s))
    
        level = 0
    
        if len(s) == 0:
            raise SyntaxError("unexpected empty string while parsing")
    
        startQuote = s[0]
        if startQuote != "\"" and startQuote != "\'":
            raise SyntaxError("string does not start with a quote: %r" % (s))
    
        c = startQuote
        for i in range(1, len(s)):
            c = s[i]
    
            if c == startQuote:
                if level % 2 == 0:
                    return {'val':s[1:i], 'level':0, 'rest':s[i+1:].lstrip()}
            elif c == "\\":
                level += 1
            else:
                level = 0
            
        # OK, we fell off the end of the string without matching the closing quote.
        # Force the string to look OK so that nobody else needs to deal with a mangled string.
        #
        add = ""
        if c == "\\" and level % 2 == 1:
            add += "\\"
       
        g.hubcmd.inform([('ParseError', CPL.qstr('appended %s to string %s' % (add, s)))],
                        src='hub')
        s += add
        return {'val':s, 'level':1, 'rest':''}
        
    kv_re = re.compile(r"""
      ^\s*                          # Ignore leading space
      (?P<key>[a-z_][a-z0-9_-]*)    # Match keyword name
      (?P<delim>$|\s*=|\s+)         # Match delimiter or equals sign
      \s*                           # Ignore spaces
      (?P<rest>.*)                  # Match eveything after the delimiter""",
                      re.IGNORECASE|re.VERBOSE)
    def parseKV(self, s):
        """ Try to parse a single KV.

        Return:
          {} on end-of-input
          { K {} rest-of-line } or
          { K V rest-of-line }
        
        """
        
        s = s.strip()
        if s == "":
            return None
    
        match = self.kv_re.match(s)
        if match == None:
            g.hubcmd.inform([('ParseError', CPL.qstr("No key-value found at '%s'" % (s)))],
                            src='hub')
            return None
        
        d = match.groupdict()
        CPL.log("Command.parseKV", "kv_re=%s" % (d))
        
        rest = d['rest']
    
        if d['delim'] == "" or d['delim'][-1] != '=':
            # If the key is not delimited by and '=', we have a valueless keyword.
            # 
            return {'key':d['key'], 'val':[], 'rest':rest}
        else:
            # Build up a list of comma-delimited values.
            #
            val = []
    
            while len(rest) != 0:
                next = rest[0]
    
                # Parse a (sub-)value
                #
                if next == "\"" or next == "\'":
                    dv = self.eatAString(rest)
    
                    if dv['level'] != 0:
                        CPL.log('parseKV', 'warning: eatAString returned with %s' % (dv))
                else:
                    dv = self.eatAVee(rest)
    
                if dv['val'] != None:
                    val.append(dv['val'])
                rest = dv['rest']
                
                # Bail out if we:
                #   - hit EOL
                #   - have no more sub-values
                #
                if len(rest) == 0 or rest[0] != ',':
                    break
                
                # Keep gathering subvalues while we find commas.
                #
                rest = rest[1:].lstrip()
                    
            return {'key':d['key'], 'val':val, 'rest':rest}

    def parse(self):
        """ Parse a raw command string into .argv """
        
        argv = collections.OrderedDict()
        rest = self.cmd
        
        while 1:
            d = self.parseKV(rest)
            if d == None:
                break
            
            if len(d['val']) == 0:
                val = None
            elif len(d['val']) == 1:
                val = d['val'][0]
            else:
                val = d['val']
            
            argv[d['key']] = val
            rest = d['rest']

        self.argv = argv
    
    def parseArgs(self):
        """ Parse a raw command string into an OrderedDict in .argDict. """
        
        if not self.argDict:
            self.argDict = Parsing.parseArgs(self.cmd)
            
    def match(self, opts):
        """ Searches an OrderedDict for matches.

        Args:
          argv - an OrderedDict of options.
          opts - a list of duples to match against. The duple parts are the option name
                 and a converter. If the converter is None, the option takes no argument.

        Returns:
          matches   - an OrderedDict of the matched options, with converted arguments.
          unmatched - a list of unmatched options from opts.
          leftovers - an OrderedDict of unmatched options from argv.

        Raises:
          Error     - Any parsing or conversion error.
        """

        self.parseArgs()
        return Parsing.match(self.argDict, opts)
    
    def coverArgs(self, requiredArgs, optionalArgs=None, ignoreFirst=None):
        """ getopt, sort of.

        Args:
           requiredArgs     - list of words which must be matched.
           optionalArgs     - list of optional words to match
           ignoreFirst      - if set, skip the first cmd word.

        Returns:
           - a dictionary of requiredArgs matches
           - a list of the requiredArgs words which were NOT matched.
           - a dictionary of optionalArgs matches
           - a list of command args not covered by requiredArgs or optionalArgs

        Notes:
           Does not return list of unmatched optionalArgs.
           Pretty much ignores argument order, for better or worse.
        
        command = 'jump height=14 over=cow before=6pm backwards 3 5 5'
        coverArgs(('height', 'backwards', 'withPole'), ('before', 'after')) ->
            {'height':14, 'backwards':None},
            ('withPole'),
            {'before':'6pm'},
            ('over=cow', '3', '5', '5')

        """

        if not hasattr(self, 'argv'):
            self.parse()
            
        CPL.log("MCCommand.coverArgs",
                "requiredArgs=%r optionalArgs=%r ignoreFirst=%r argv=%r" \
                % (requiredArgs, optionalArgs, ignoreFirst, self.argv))

        # Start with a copy of the command args, which we consume as we copy to
        # the matched_args dict.
        #
        # Match requireArgs before optionalArgs
        #
        if requiredArgs:
            requiredArgs = list(requiredArgs)
        else:
            requiredArgs = []
        if optionalArgs:
            optionalArgs = list(optionalArgs)
        else:
            optionalArgs = []
        
        requiredMatches = {}
        optionalMatches = {}
        leftovers = []

        # Walk down the argument list and categorize the arguments.
        #
        for k in self.argv:
            v = self.argv[k]
            if k in requiredArgs:
                requiredMatches[k] = v
                requiredArgs.remove(k)
            elif k in optionalArgs:
                optionalMatches[k] = v
                optionalArgs.remove(k)
            else:
                leftovers.append((k,v))

        CPL.log("MCCommand.coverArgs",
                "raw=%r requiredMatches=%r optionalMatches=%r unmatched=%r leftovers=%r" \
                % (self.argv, requiredMatches, optionalMatches, requiredArgs, leftovers))
                
        return requiredMatches, requiredArgs, optionalMatches, leftovers


    def addReply(self, reply, **argv):
        self.respond(reply['flag'], KVs=reply['KVs'], **argv)
        
    def inform(self, KVs='', **argv):
        self.makeAndSendReply('i', KVs, **argv)

    def warn(self, KVs='', **argv):
        self.makeAndSendReply('w', KVs, **argv)

    def diag(self, KVs='', **argv):
        self.makeAndSendReply('d', KVs, **argv)

    def finish(self, KVs='', **argv):
        if self.neverEnd:
            self.makeAndSendReply('i', KVs, **argv)
        else:
            self.makeAndSendReply(':', KVs, **argv)

    def fail(self, KVs='', **argv):
        if self.neverEnd:
            self.makeAndSendReply('w', KVs, **argv)
        else:
            self.makeAndSendReply('f', KVs, **argv)

    def respond(self, flag, KVs='', **argv):
        """ Respond with a specified flag. """
        
        self.makeAndSendReply(flag, KVs, **argv)

    def makeAndSendReply(self, flag, KVs, **argv):
        """ Bundle a flag and some KVs into a proper Reply & ship it off. """
        
        src = argv.get('src', self.actorName)
        bcast = argv.get('bcast', True)
        
        if self.debug > 0:
            CPL.log("Command.makeAndSendReply", "src = %r, flag = %s, KVs = %r" % (src, flag, KVs))
        
        r = Reply(self, flag, KVs, src=src, bcast=bcast)
        self.reply(r, **argv)
        
    def reply(self, r, **argv):
        """ Finally register a Reply's KVs and offer it to any interested parties."""

        if self.debug > 1:
            CPL.log("Command.sendReply", "reply = %r" % (r))

        if not argv.get('noRegister', False):
            g.KVs.setKVsFromReply(r)

        for c in g.commanders.values():
            c.tasteReply(r)
            
        if r.finishesCommand():
            # del g.pendingCommands[self.xid]
            if self.bcastCmdInfo:
                g.hubcmd.diag("CmdDone=%s,%s" % (self.xid, CPL.qstr(r.flag.lower())),
                              src="cmds")
            
