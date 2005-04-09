""" Command.py -- essentials of hub commands.

    When commands come in from the hub or some other source, a Command
    instance is created to shepherd it though to completion. A
    Command knows what the command is and where it came from, and provides
    wrappers for responding to the sender.
    
"""
__all__ = ['Command']

from RO.Alg import OrderedDict
import CPL.log as log
import Parsing

class Command(object):
    def __init__(self, source, username, mid, cid, cmd, **argv):
        """ Create a fully defined command:

        source  - The input object that gets any responses.
        username - the username of the commander.
        mid 	- Message ID: should uniquely identify the command.
        cid 	- Connection ID: might identify this connection.
        cmd	- The command proper.

        """
        
        self.source = source
        self.fullname = username
        self.cmdrName = username
        self.mid = mid
        self.cid = cid
        self.raw_cmd = cmd
        
        self.alive = 1
        self.debug = argv.get('debug', 0)

        if self.debug > 4:
            CPL.log("Command", self)
            
        self.__parse()
        
    def __str__(self):
        return "Command(CLIENT source=%s fullname=%s cid=%s mid=%s cmd=%r)" % \
               (self.source, self.fullname, self.cid, self.mid, self.raw_cmd)

    def __parse(self):
        """ parse .raw_cmd into .argDict. """

        self.argDict = Parsing.parseArgs(self.raw_cmd)
        self.argv = self.argDict.keys()
        if self.debug > 4:
            CPL.log("MCCommand.parse", "new command mid=%s cid=%s source=%s cmd=%r" % \
                    (self.mid, self.cid, self.source, self.raw_cmd))

    def program(self):
        """ Return the program name component of the username. """

        program = None
        try:
            parts = self.fullname.split('.')
            program = parts[0]
        except:
            CPL.log("Command.program", "failed to split fullname")

        return program

    def username(self):
        """ Return the program name component of the username. """

        username = None
        try:
            parts = self.fullname.split('.')
            username = parts[1]
        except:
            CPL.log("Command.program", "failed to split fullname")

        return username

    def qstr(self, o):
        """ Convert o as a possibly quoted string to a string.

        If o is quoted, strip the quotes.
        """

        s = str(o)
        if len(s) >= 2:
            s0 = s[0]
            if s0 in ('"', "'") and s[-1] == s0:
                return s[1:-1]
        return s
    
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

        if self.debug > 4:
            CPL.log("MCCommand.coverArgs",
                    "requiredArgs=%r optionalArgs=%r ignoreFirst=%r argDict=%r" \
                    % (requiredArgs, optionalArgs, ignoreFirst, self.argDict))

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
        if ignoreFirst:
            assert 0==1, "ignoreFirst not implemented yet."

        for k, v in self.argDict.iteritems():
            if k in requiredArgs:
                requiredMatches[k] = v
                requiredArgs.remove(k)
            elif k in optionalArgs:
                optionalMatches[k] = v
                optionalArgs.remove(k)
            else:
                leftovers.append((k,v))

        if self.debug > 3:
            CPL.log("Command.coverArgs",
                    "raw=%r requiredMatches=%r optionalMatches=%r unmatched=%r leftovers=%r" \
                    % (argDict, requiredMatches, optionalMatches, requiredArgs, leftovers))
                
        return requiredMatches, requiredArgs, optionalMatches, leftovers

    def isAlive(self):
        """ Is this command still valid (i.e. no fail or finish sent)? """

        return self.alive
    
    def warn(self, response):
        """ Return warning. """

        self.__respond('w', response)
        
    def respond(self, response):
        """ Return intermediate response. """

        self.__respond('i', response)
        
    def finish(self, response=None):
        """ Return successful command finish. """

        if response == None:
            response = ''
            
        self.__respond(':', response)
        self.alive = 0
        
    def fail(self, response):
        """ Return failure. """

        self.__respond('f', response)
        self.alive = 0
        
    def __respond(self, flag, response):
        """ Send a response via our source. """
        
        self.source.sendResponse(self.mid, self.cid, flag, response)
        
    def sendResponse(self, flag, response):
        """ Actually send the response to the appropriate source. If the command is
            still active, send to the originating source. Otherwise try sending something 
            informative to the catchall source of last resort. """
            
        if self.alive:
            self.source.sendResponse(self.mid, self.cid, flag, response)
        else:
            self.catchall.respond("noMID='mid=%d cid=%d flag=%s response=%r'" %
                                  (self.mid, self.cid, flag, response))
            
if __name__ == "__main__":
    c = Command(1, 2, None, "tcmd arg1=v1 arg2=v2 arg3 arg4 arg5='v5' 3 3 5 acb=99", None)

    requiredMatches, requiredArgs, optionalMatches, leftovers = \
                     c.coverArgs(('arg1', 'xxx', 'arg4'), ('arg3', 'arg5', 'noarg'))
    requiredMatches, requiredArgs, optionalMatches, leftovers = \
                     c.coverArgs(None, None, 'tcmd')
