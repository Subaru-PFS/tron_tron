__all__ = ['perms']

import time
import os

import CPL
from Hub.KV.KVDict import *
from Vocab.InternalCmd import *
import g
import hub

class perms(InternalCmd):
    """ All the commands that the "perms" package provides.
        To wit:

          perms status
          perms lock a1 a2 a3
          perms lock *
          perms unlock a1 a2 a3
          perms unlock *

          perms register PROGRAM
          perms drop PROGRAM
          
          perms CMD program=P 

          CMD:
            set a1 a2 a3
            add a1 a2
            drop a1 a2
            
        Keywords returned:
          actors=a1,a2,a3
          authList=c,a1,a2,a3
          lockedActors=a1,a2
    """
    
    def __init__(self, **argv):
        argv['needsAuth'] = True
        argv['safeCmds'] = '^\s*status\s*$'
        InternalCmd.__init__(self, 'perms', **argv)

        self.commands = {'status': self.status,
                         'lock': self.lockCmd,
                         'unlock': self.unlockCmd,
                         'setLocked': self.setLockedCmd,
                         'set': self.setCmd,
                         'add': self.addCmd,
                         'drop': self.dropCmd,
                         'register' : self.registerCmd,
                         'unregister' : self.unregisterCmd,
                         'hackOn' : self.hackOn,
                         'hackOff' : self.hackOff

                         }
        
    def help(self, cmd, finish=True):
        pass
    
    def hackOn(self, cmd, finish=True):
        g.perms.hackOn = True
        cmd.warn('permsTxt="permissions are now disabled"')
        cmd.finish()
        
    def hackOff(self, cmd, finish=True):
        g.perms.hackOn = False
        cmd.warn('permsTxt="permissions are now in effect"')
        cmd.finish()
        
    def status(self, cmd, finish=True):
        """ Return the authentication keywords. """

        # Ignore any other arguments.
        #
        g.perms.status(cmd=cmd)

        if finish:
            cmd.finish()
            
    # auth.statusCmd.help = ('status', 'Return the authorization status keywords.', None)
                           
    def setLockedCmd(self, cmd, finish=True):
        """ Lock a list of actors from non-APO commanders.

        Usage:
           setLocked a1 [a2 ...]
           setLocked *
        """

        args = cmd.argDict.keys()[1:]
        if len(args) == 1 and args[0] == '*':
            actors = None
        else:
            actors = args

        g.perms.setLockedActors(actors, cmd=cmd)

        if finish:
            cmd.finish()
        
    def lockCmd(self, cmd, finish=True):
        """ Lock a list of actors from non-APO commanders.

        Usage:
           lock a1 [a2 ...]
           lock *
        """

        args = cmd.argDict.keys()[1:]
        if len(args) == 1 and args[0] == '*':
            actors = []
        else:
            actors = args

        g.perms.lockActors(actors, cmd=cmd)

        if finish:
            cmd.finish()
        
    def unlockCmd(self, cmd, finish=True):
        """ unlock a list of actors from non-APO commanders.

        Usage:
           unlock a1 [a2 ...]
           unlock *
        """

        args = cmd.argDict.keys()[1:]

        if len(args) == 1 and args[0] == '*':
            actors = []
        else:
            actors = args

        g.perms.unlockActors(actors, cmd=cmd)

        if finish:
            cmd.finish()
        
    def registerCmd(self, cmd, finish=True):
        """ Register a list of programs to control.

        Usage:
           register p1 [p2 ...]
           register *
        """

        args = cmd.argDict.keys()[1:]
        if len(args) == 0:
            cmd.fail('text="perms register requires one or more program names"')
            return
        
        if len(args) == 1 and args[0] == '*':
            programs = []
        else:
            programs = args

        g.perms.addPrograms(programs, cmd=cmd)

        if finish:
            cmd.finish()
        
    def unregisterCmd(self, cmd, finish=True):
        """ Unregister a list of programs to control.

        Usage:
           unregister p1 [p2 ...]
           unregister *
        """

        args = cmd.argDict.keys()[1:]
        if len(args) == 0:
            cmd.fail('text="perms unregister requires one or more program names"')
            return

        if len(args) == 1 and args[0] == '*':
            programs = []
        else:
            programs = args

        g.perms.dropPrograms(programs, cmd=cmd)

        if finish:
            cmd.finish()
        
    def setCmd(self, cmd, finish=True):
        """ Define the actors that a given program can command.

        Usage:
           set prog=p [a1 ...]
        """

        matched, unmatched, leftovers = cmd.match([('set', None),
                                                   ('program', str)])

        try:
            program = matched['program']
        except KeyError:
            cmd.fail('authTxt="no program specified"')
            return

        g.perms.setActorsForProgram(program, leftovers, cmd=cmd)

        if finish:
            cmd.finish()
        

    def addCmd(self, cmd, finish=True):
        """ Add to the actors that a given program can command.

        Usage:
           add program=p [a1 ...]
        """

        matched, unmatched, leftovers = cmd.match([('add', None),
                                                   ('program', str)])

        try:
            program = matched['program']
        except KeyError:
            cmd.fail('authTxt="no program specified"')
            return

        g.perms.addActorsToProgram(program, leftovers, cmd=cmd)

        if finish:
            cmd.finish()
        
    def dropCmd(self, cmd, finish=True):
        """ Block some actors that a given program can command.

        Usage:
           drop program=p [a1 ...]
        """

        matched, unmatched, leftovers = cmd.match([('drop', None),
                                                   ('program', str)])

        try:
            program = matched['program']
        except KeyError:
            cmd.fail('authTxt="no program specified"')
            return

        g.perms.dropActorsFromProgram(program, leftovers, cmd=cmd)

        if finish:
            cmd.finish()
        

def _test():
    a = auth()
    a.statusCmd
    
if __name__ == "__main__":
    _test()
    
    
