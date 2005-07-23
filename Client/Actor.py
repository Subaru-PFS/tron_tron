__all__ = ['Actor']

import gc
import inspect
import pprint
import sys
import types
import traceback
from threading import *

import CPL
import RO

import Command
import FilterQueue
import FullReply
import HubLink

class Acting(object):
    """ A base class which provides scriptable actor behavior.
    """
    
    def __init__(self, actor, **argv):
        self.actor = actor
        self.debug = argv.get('debug', 0)

        assert isinstance(self.actor, Actor), "self.actor != Actor (%s)" % (self.actor)
                    
    def callback(self, target, cmdString, callback=None, responseTo=None, dribble=False):
        return self.actor.sendCommand(target, cmdString, callback, responseTo=responseTo, dribble=dribble)
        
    def call(self, target, cmdString, responseTo=None):
        raise Exception("Acting cannot send blocking commands.")
        # return self.actor.sendCommand(target, cmdString, callback, responseTo=responseTo, dribble=dribble)
        
class Actor(Thread):
    """ Actors implement a single-threaded command processor that can also send commands.
    
    The external input interface is a Queue.
    
    """

    def __init__(self, name, **argv):
        Thread.__init__(self)
        self.setName(name)
        self.setDaemon(True)
        
        self.name = name
        self.debug = argv.get('debug', 0)
        self.queue = FilterQueue.ActorFilter(name=self.name, debug=self.debug)

        self.nullCmd = Command.Command(self.name, 0, 0, self.name, '')
        
        self.mid = 1
        self.commands = RO.Alg.OrderedDict({'help': self.helpCmd,
                                            'ping': self.pingCmd,
                                            'dbg' : self.debugCmd,
                                            'gc'  : self.gcCmd,
                                            'wing': self.doWing,
                                            'refs' : self.memRefsCmd})

        # Generic help template.
        #
        self.helpText = ("%s COMMAND" % (self.name), "   COMMAND is one of:")

    def _getFuncHelp(self, name):
        """ Return a command handler's list of help string, or make up a list.

        Args:
            name   - the name of a command expected in .commands
        """

        l = []
        if name not in self.commands:
            return None

        try:
            eval("funcHelp = self.%s.helpText" % (name))
        except Exception, e:
            CPL.log('Actor._getFuncHelp', CPL.qstr('error getting help text: %s' % e))
            funcHelp = ["%s  - no help" % (name)]
            
        return funcHelp

    def memRefsCmd(self, cmd):
        d = {}
        sys.modules
        # collect all classes
        for m in sys.modules.values():
            for sym in dir(m):
                o = getattr (m, sym)
                if type(o) in (types.ClassType, types.TypeType):
                    d[o] = sys.getrefcount (o)
        # sort by refcount
        pairs = map (lambda x: (x[1],x[0]), d.items())
        pairs.sort()
        pairs.reverse()

        for n, c in pairs[:100]:
            CPL.log('memrefs', '%10d %s' % (n, c.__name__))

    def gcCmd(self, cmd):
        d = {}
        sys.modules
        # collect all classes
        for m in sys.modules.values():
            for sym in dir(m):
                o = getattr (m, sym)
                if type(o) in (types.ClassType, types.TypeType):
                    d[o] = sys.getrefcount (o)
        # sort by refcount
        pairs = map (lambda x: (x[1],x[0]), d.items())
        pairs.sort()
        pairs.reverse()

        for n, c in pairs[:100]:
            CPL.log('memrefs', '%10d %s' % (n, c.__name__))


    def doWing(self, cmd):
        import wingdbstub
        
    def debugCmd(self, cmd):
        """ Execute a command
        """

        cmdTxt = cmd.raw_cmd.strip()
        cmdTxt = cmdTxt[4:].strip()
        
        CPL.log("%sDebugCmd" % (self.name), "cmd = %r" % (cmdTxt))
        if cmdTxt == "":
            cmd.finish("Eval=%s" % (CPL.qstr("")))
            return
    
        try:
            ret = eval(cmdTxt)
        except Exception, e:
            cmd.fail('%sEvalError=%s' % (self.name, CPL.qstr(e)))
            raise
    
        cmd.finish("%sEval=%s" % (self.name, CPL.qstr(ret)))
        CPL.log("%s.debugCmd" % (self.name), "ret = %r" % (ret))
        
    def pingCmd(self, cmd):
        """ Acknowledge our existence. """

        cmd.finish('text="%s is alive"' % (self.name))
        
    def helpCmd(self, cmd):
        """ Return help strings.

        CmdArgs:
             none           - print help text for all commands
             command names  - print help text for the given commands.
             
        The object might have a .helpText, and each individual .commands handler might have one.

        """

        # Build the list of help strings. Either all help, or help for the given commands.
        # If a command name is bogus, print all help.
        #
        helpList = []
        if len(cmd.argDict) > 1:
            for cmdName in cmd.argDict.keys[1:]:
                funcHelp = self._getFuncHelp(cmdName)

                # If anything is wrong, print all the help.
                if funcHelp == None:
                    helpList = []
                    break

                helpList += funcHelp

        if not helpList:
            helpList = []
            helpList += self.helpText
            for c in self.commands:
                helpList += self._getFuncHelp(c)

        # Prepass to get the lengths of the command synopses
        maxlen = 0
        for help in helpList:
            if type(help) == type(''):
                l = len(help)
            else:
                l = len(help[0])
            if l > maxlen:
                maxlen = l

        for help in helpList:
            if type(help) == type(''):
                syn, body = help, ''
            elif len(help) == 1:
                syn, body = help[0], ''
            else:
                syn, body = help[0], help[1:]
            cmd.respond("helpTxt=%*s - %s" % (maxlen, 
                                              CPL.qstr(syn), CPL.qstr(body)))
        cmd.finish('')
    helpCmd.helpText = ("help", "you got it!")

    def _parse(self, cmd):
        """ Default parsing behavior. Simply calls a Command's handler.

        Args:
            cmd  - a Command instance. The first word of the command text is used
                   as a key in .commands.

        If the command word is found, the handler is called. If not, the command is failed.
        """

        if self.debug >= 0:
            CPL.log(self.name, "new command: %s" % (cmd.raw_cmd))
            
        # Actively reject empty commands. Maybe this should just ignore them.
        #
        if len(cmd.argDict) == 0:
            cmd.warn('%sTxt="empty command"' % (self.name))
            cmd.finish()
            return
        
        # Find the handler and call it.
        #
        cmdWords = cmd.argDict.keys()
        cmdWord = cmdWords[0]
        handler = self.commands.get(cmdWord, None)
        if not handler:
            cmd.fail('%sTxt=%s' % (self.name,
                                   CPL.qstr('unknown command %s, try one of %s') % \
                                   (cmdWord, ', '.join(self.commands.keys()))))
            return
        handler(cmd)
        
        
    def parse(self, cmd):
        CPL.log("parse", "parsing cmd %s" % (cmd))
        try:
            self._parse(cmd)
        except Exception, e:
            cmd.fail('%sTxt=%s' % (self.name, CPL.qstr(e, tquote='"')))
            CPL.log(self.name, "exception=%s" % (e))

            tracelist = inspect.trace()
            toptrace = tracelist[-1]
            tp = pprint.pformat(toptrace)
            tloc = pprint.pformat(toptrace[0].f_locals)
            tvar = pprint.pformat(toptrace[0].f_code.co_varnames)

            ex_list = traceback.format_exception(sys.exc_type, sys.exc_value, sys.exc_traceback)
            one_liner = "%s: %s" % (sys.exc_type, sys.exc_value)
            CPL.error('%s.main' % (self.name), "======== Top level exception: %s" % (''.join(ex_list)))
            CPL.error('%s.main' % (self.name), "==== trace : %s" % (''.join(tp)))
            CPL.error('%s.main' % (self.name), "==== locals: %s" % (''.join(tloc)))
            CPL.error('%s.main' % (self.name), "==== vars  : %s" % (''.join(tvar)))


    def run(self):
        while 1:
            # We may want to switch to blocking on a Condition or Event, which would
            # give us the ability to timeout.
            #
            obj = self.queue.get()

            if 1 or self.debug > 5:
                CPL.log("Actor.run", "obj=%s" % (obj))

            # Pass exceptions on to higher level.
            #
            if isinstance(obj, Exception):
                raise obj

            if isinstance(obj, float):
                hitTimeout = self.checkTimeout(obj)
                
            # Pass new commands on to the parser
            if isinstance(obj, Command.Command):
                self.parse(obj)
            else:
                self.__newReply(obj)

    def checkTimeout(self, t):
        """ Check whether we have exceeded any timeout. If so, clean up and bail. """

        pass

    def __newReply(self, reply):
        if self.debug >= 0:
            CPL.log("Actor.newReply", "reply=%s" % (reply))

        key = int(reply.cmdrMid)
        cmd = self.commands[key]

        if self.debug >= 0:
            CPL.log("Actor.newReply", "cmd=%s" % (cmd))

        if reply.flag in 'fF:':
            self.queue.removeCommand(cmd['command'])
            del self.commands[key]

        if cmd['dribble']:
            cb = cmd['callback']
            if cb:
                cb(reply)
        else:
            cmd['replies'].append(reply)
            if reply.flag in 'fF:':
                all = { 'lines':cmd['replies'],
                        'ok':bool(reply.flag == ':')
                        }
                cb = cmd['callback']
                if cb:
                    cb(all)
                    
    def sendCommand(self, actor, cmd, callback, responseTo=None, dribble=False, timeout=0):
        """ Send command string cmd to the named actor. Optionally indicate which command we are acting
        on behalf of.
        """

        if responseTo == None:
            cid = self.name
        else:
            cid = "%s.%s" % (responseTo.fullname, self.name)
            
        mid = self.mid
        self.mid += 1
        
        command = HubLink.Command(cid, mid, actor, cmd)
        self.commands[mid] = { 'callback':callback,
                               'cid':cid,
                               'mid':mid,
                               'replies':[],
                               'dribble':dribble,
                               'timeout':timeout,
                               'command':command
                               }
        
        self.queue.addCommand(command)
        hubLink.toHub.sendCommand(command)

    def cidForCmd(self, cmd):
        """ Return a proper cid for a command that we send in response"""

        return "%s.%s" % (cmd.fullname, self.name)
    
