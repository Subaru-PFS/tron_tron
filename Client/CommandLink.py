__all__ = ['CommandNub', 'connect']

import os
import re
import sys

from Client import Command
import CPL
import IO

class CommandNub(IO.IOHandler):
    # How we match a command...
    #
    cmdRe = re.compile("""
    \s*
    (?P<username>[a-z0-9_.-]+)
    \s*
    (?P<mid>[0-9]+)
    \s+
    (?P<cid>[a-z0-9_][a-z0-9_.]*)
    \s+
    (?P<cmd>.*)""",
                       re.IGNORECASE | re.VERBOSE)

    def __init__(self, poller, queue, **argv):
        argv.setdefault('in_f', sys.stdin)
        argv.setdefault('out_f', sys.stdout)
        IO.IOHandler.__init__(self, poller, **argv)
        self.inputBuffer = ""
        self.queue = queue
        self.EOL = '\n'

        self.sendResponse(1,1,':','hello')
        
    def shutdown(self, why="cuz"):
        CPL.log("CommandLink.shutdown", "shutdown because %s" % (why))
        sys.exit("exiting because %s" % (why))
        os._exit(1)
    
    def decode(self, buf, newData):
        """ Decode and return a new, complete command. """

        if newData:
            buf += newData
        
        eol = buf.find(self.EOL)        

        # No complete command found. Return the original buffer so that the caller
        # can easily determine that no input was consumed.
        #
        if eol == -1:
            return None, buf

        cmdString = buf[:eol]
        buf = buf[eol+len(self.EOL):]

        # Consume leading EOL.
        if eol == 0:
            return None, buf
        
        match = self.cmdRe.match(cmdString)

        if match == None:
            raise CPL.Error("Command could not be parsed: %s" % (CPL.qstr(cmdString)),
                            unparsed=buf)

        else:
            d = match.groupdict()
            mid = int(d['mid'])
            
            return Command.Command(self, d['username'], d['cid'], mid, d['cmd']), buf

    def copeWithInput(self, s):
        """ Incorporate new input: buffer it, then extract and operate on each complete command.

        Args:
           s   - the new, but still unbuffered, input.
        """

        if self.debug > 5:
            CPL.log('CommandNub.copeWithInput', "read: %s" % (s))

        # Find and execute _every_ complete input.
        # The only time this function gets called is when new input comes in, so we
        # have no reliable mechanism for deferring input. If we need to, we could
        # adapt the PollHandler to query for unconsumed input. Hmm, maybe not.
        #
        while 1:
            try:
                cmd, leftover = self.decode(self.inputBuffer, s)
                s = None
            except CPL.Error, e:
                self.inputBuffer = e.unparsed
                raise
            
            self.inputBuffer = leftover
            if cmd == None:
                break

            self.queue.copeWithInput(cmd)
        
    def sendResponse(self, mid, cid, flag, response):
        e = "%s %s %s %s\n" % (cid, mid, flag, response)
        if self.out_f == None:
            print e
        else:
            self.queueForOutput(e)
            
def connect(poller, queue, **argv):
    
    nub = CommandNub(poller, queue, **argv)
    
    return nub
