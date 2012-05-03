""" Auth.py - maintain authorization tables: who can command which actors?
"""

__all__ = ['Auth']

import re

import CPL
import g

class Auth(CPL.Object):
    """
    Maintain an authorization table between commanders and actors. 
    
    Basics:
       - A certain number of actors are registered with this package.
       - 

    """
    
    def __init__(self, defaultCmd, **argv):
        CPL.Object.__init__(self, **argv)

        self.defaultCmd = defaultCmd
        self.programs = {}
        self.actors = {}                # The actors subject to permissions.
        self.lockedActors = {}

        self.hackOn = False
        self.gods = ("APO", "TU02")

        for a in ['perms']:
            self.actors[a] = True
            
        # Gods are special: They:
        #  - can _always_ command "perms"
        #  - can command newly added actors.
        #
        self.addPrograms(self.gods, ["perms"])
        self.status()
        
    def checkAccess(self, cmdr, actor, cmd=None):
        """Return whether the given cmdr may command the given actor.

        Rules:
           - If the actor is locked, only allow APO users to command it.
           - If the program is unknown, deny access.
           - Otherwise check the program's access list.
        """

        program = cmdr.split('.', 1)[0]
        if self.debug > 5:
            CPL.log("Auth.checkAccess", "checking %s (%s) -> %s" % (cmdr, program, actor))
            
        if not cmd:
            cmd = self.defaultCmd

        # Do we enforce authorization at all? If so, which actor do we use, only for authorization?
        authName = actor.needsAuth
        if not authName:
            return True
        actorName = actor.name

        # We can lock actors that we ordinarily don't know about, so check .lockedActors first
        if authName in self.lockedActors:
            access = program in self.gods
            if access:
                return True
            else:
                cmd.warn("text=%s" % (CPL.qstr("%s is locked by APO" % (actorName))))
                return False

        # If we don't know about an actor, let the command go through
        if authName not in self.actors:
            if self.hackOn:
                CPL.log("Auth.checkAccess", "unregistered actor %s" % (actorName))
            return True

        # If the command is declared safe by the actor, let it go though.
        safeCmds = actor.safeCmds
        CPL.log("auth.checkAccess", "checking '%s' against %s" % (cmd.cmd, safeCmds))
        if safeCmds != None and cmd.cmd != None:
            if safeCmds.search(cmd.cmd):
                return True

        # Let the hub command anything. This is for initialization commands, etc.
        if program == 'hub':
            return True
        
        # But if we don't know about a _program_, block the command.
        #
        try:
            accessList = self.programs[program]
            if self.debug > 5:
                CPL.log("Auth.checkAccess", "cmdr %s accessList = %s" % (cmdr, accessList))

                ok = authName in accessList

                if self.hackOn:
                    CPL.log("Auth.checkAccess", "actor in accessList = %s" % (ok))
                    return True
                else:
                    return ok
        except KeyError:
            # For SDSS, if permissions are disabled do not generate annoying warnings.
            if self.hackOn:
                return True

            # In this case, send a warning to our .defaultCmd as well as to the affected cmd
            cmd.warn("permsTxt=%s" % (CPL.qstr("Authorization table has no entry for program: %s" % (program))))
            if cmd != self.defaultCmd:
                self.defaultCmd.warn("permsTxt=%s" % (CPL.qstr("Authorization table has no entry for program: %s" % (program))))
            if self.hackOn:
                CPL.log("Auth.checkAccess", "unknown program %s" % (program))
                return True
            else:
                return False

    def status(self, cmd=None):
        """ Generate all our keys. 

        Args:
          cmd       - if set, the command to reply to. Otherwise use our .defaultCmd
          
        """
        
        self.genActorsKey(cmd=cmd)
        self.genProgramsKey(cmd=cmd)
        self.genLockedKey(cmd=cmd)
        self.genAuthKeys(cmd=cmd)
        
    def genActorsKey(self, cmd=None):
        """ Generate key describing the actors we control access to.

        Args:
           cmd       - if set, the command to reply to. Otherwise use our .defaultCmd

        Notes:
           Never finishes the cmd.
        """

        if not cmd:
            cmd = self.defaultCmd

        actors = self.actors.keys()
        actors.remove('perms')
        actors.sort()
        actors = [CPL.qstr(x) for x in actors]

        # HACK - older TUIs do not like empty variables ("name=")
        if actors:
            cmd.inform("actors=%s" % (','.join(actors)))
        else:
            cmd.inform("actors")
            
        
    def genProgramsKey(self, cmd=None):
        """ Generate key describing the programs we control access to.

        Args:
           cmd       - if set, the command to reply to. Otherwise use our .defaultCmd

        Notes:
           Never finishes the cmd.
        """

        if not cmd:
            cmd = self.defaultCmd

        programs = self.programs.keys()
        programs.sort()
        programs = [CPL.qstr(x) for x in programs]

        # HACK - older TUIs do not like empty variables ("name=")
        if programs:
            cmd.inform("programs=%s" % (','.join(programs)))
        else:
            cmd.inform("programs")
            
        
    def genLockedKey(self, cmd=None):
        """ Generate key describing the locked actors.

        Args:
           cmd    - if set, the command to reply to. Otherwise use our .defaultCmd

        Notes:
           Never finishes the cmd.
        """

        if not cmd:
            cmd = self.defaultCmd

        actors = self.lockedActors.keys()
        actors.sort()
        actors = [CPL.qstr(x) for x in actors]

        # HACK - older TUIs do not like empty variables ("name=")
        if actors:
            cmd.inform("lockedActors=%s" % (','.join(actors)))
        else:
            cmd.inform("lockedActors")

    def addActors(self, actors, cmd=None):
        """ Register a list of actors to be controlled.

        """

        if not cmd:
            cmd = self.defaultCmd
            
        if self.debug > 3:
            CPL.log("auth.addActors", "adding actors %s" % (actors))

        for a in actors:
            if a in self.actors:
                cmd.warn("permsTxt=%s" % (CPL.qstr("Actor %s is already registered for access control." % (a))))
            else:
                self.actors[a] = True

        # Prime superusers to be able to command newly connected actors
        #
        for g in self.gods:
            self.addActorsToProgram(g, actors)
            
        self.genActorsKey(cmd=cmd)
        
    def setLockedActors(self, actors, cmd=None):
        """ Block non-APO users form commanding a list of actors.

        Any actors not in .actors will be ignored with a warning. This may not be the right behavior. We may
        actually want to allow actors we do not control to be locked.

        Args:
           actors   - if None, lock all .actors. Else clear all existing locks and add the given actors.
        """

        if not cmd:
            cmd = self.defaultCmd
            
        if actors == None:
            actors = self.actors
                
        if self.debug > 3:
            CPL.log("auth.lockActor", "locking actors %s" % (actors))

        self.lockedActors = {}
        for a in actors:
            if a not in self.actors:
                cmd.warn("permsTxt=%s" % (CPL.qstr("Actor %s is not subject to permissions and will not be locked" % (a))))
            else:
                self.lockedActors[a] = True

        self.genLockedKey(cmd=cmd)
        
    def lockActors(self, actors, cmd=None):
        """ Block non-APO users form commanding a list of actors.

        Any actors not in .actors will be ignored with a warning. This may not be the right behavior. We may
        actually want to allow actors we do not control to be locked.
        """

        if not cmd:
            cmd = self.defaultCmd
            
        if not actors:
            actors = self.actors
                
        if self.debug > 3:
            CPL.log("auth.lockActor", "locking actors %s" % (actors))

        for a in actors:
            if a in self.lockedActors:
                cmd.warn("permsTxt=%s" % (CPL.qstr("Actor %s is already locked" % (a))))
            elif a not in self.actors:
                cmd.warn("permsTxt=%s" % (CPL.qstr("Actor %s is not subject to permissions and will not be locked" % (a))))
            else:
                self.lockedActors[a] = True

        self.genLockedKey(cmd=cmd)
        
    def unlockActors(self, actors, cmd=None):
        """ unblock non-APO users from commanding a list of actors.
        """

        if not cmd:
            cmd = self.defaultCmd
            
        if not actors:
            actors = self.lockedActors

        if self.debug > 3:
            CPL.log("auth.unlockActor", "unlocking actors %s" % (actors))

        for a in actors:
            try:
                del self.lockedActors[a]
            except KeyError:
                cmd.warn("permsTxt=%s" % (CPL.qstr("Actor %s was not locked" % (a))))

        self.genLockedKey(cmd=cmd)
        
    def genAuthKeys(self, programs=None, cmd=None):
        """ Generate keys describing some or all programs.

        Args:
           cmd       - if set, the command to reply to. Otherwise use our .defaultCmd
           programs  - if set, a list of programs to generate keys for. Otherwise describe all programs.

        Notes:
           Never finishes the cmd.
        """

        if not cmd:
            cmd = self.defaultCmd
        if not programs:
            programs = self.programs.keys()

        programs.sort()
        CPL.log("auth.genAuthKeys", "listing programs: %s" % (programs))

        for prog in programs:
            try:
                pAuth = self.programs[prog].keys()
            except KeyError, e:
                raise Exception("No authorization entry found for program %s" % (prog))
            
            pAuth.sort()
            actors = [CPL.qstr(x) for x in pAuth]
            cmd.inform("authList=%s,%s" % (CPL.qstr(prog), ','.join(actors)))
        
    def addPrograms(self, programs=[], actors=[], cmd=None):
        """ Add a list program to the control list.

        Args:
          program   - a list of program names. Use all connected programs if empty.
          actors    - an optional list of actors that the commander can command.
        """

        if not cmd:
            cmd = self.defaultCmd

        if not programs:
            programs = []
            for name, cmdr in g.commanders.iteritems():
                if cmdr.needsAuth and name not in self.programs:
                    programs.append(name)

        if self.debug > 3:
            CPL.log("auth.addPrograms",
                    "adding programs %s with actors=%s" % (programs, actors))

        for prog in programs:
            if prog in self.programs:
                cmd.warn("permsTxt=%s" % \
                         (CPL.qstr("Program %s already has an authorization entry, which will not be modified." % (prog))))
                continue
            self.programs[prog] = {}
            self.setActorsForProgram(prog, actors, cmd=cmd)
        self.genProgramsKey(cmd=cmd)
        
    def dropPrograms(self, programs=[], cmd=None):
        """ Remove a list of programs from the control list.

        Args:
           programs  - a list of programs to register for authorization. Adds all connected
                       programs if empty.
           cmd       - The command to reply to, or .defaultCmd
        """

        if not programs:
            programs = self.programs.keys()

        if self.debug > 3:
            CPL.log("auth.dropProgram", "dropping programs %s" % (programs))

        if not cmd:
            cmd = self.defaultCmd

        for program in programs:
            if program in self.gods:
                cmd.warn("permsTxt=%s" % \
                         (CPL.qstr("Super-%s cannot be removed from the list of authorized programs" % (program))))
                self.genAuthKeys([program], cmd)
                continue
            try:
                del self.programs[program]
            except:
                cmd.warn("permsTxt=%s" % \
                         (CPL.qstr("Program %s did not have an authorization entry, so could not be deleted" % (program))))
            
        self.genProgramsKey(cmd=cmd)
    
    def setActorsForProgram(self, program, actors, cmd=None):
        """ Define the list of actors that a program can command.
        """

        if self.debug > 3:
            CPL.log("auth.setActors", "setting actors for commander %s: %s" % (program, actors))
            
        if not cmd:
            cmd = self.defaultCmd

        if program not in self.programs:
            cmd.fail("permsTxt=%s" % (CPL.qstr("Program %s did not have an authorization entry, so could not be set" % (program))))
            return
        
        d = {}
        for a in actors:
            if a not in self.actors:
                cmd.warn("permsTxt=%s" % (CPL.qstr("Actor %s is not subject to permissions." % (a))))
            else:
                d[a] = True
            
        # Make sure God-like commanders can always command us...
        #
        if program in self.gods:
            d['perms'] = True
        self.programs[program] = d

        self.genAuthKeys(programs=[program], cmd=cmd)
        
    def addActorsToProgram(self, program, actors, cmd=None):
        """ Add a list of actors to a actor's authorized list
        """

        if not cmd:
            cmd = self.defaultCmd

        if self.debug > 3:
            CPL.log("auth.addActors", "adding actors for program %s: %s" % (program, actors))
            
        try:
            d = self.programs[program]
        except KeyError, e:
            cmd.fail("permsTxt=%s" % (CPL.qstr("Program %s did not have an authorization entry, so could not be added to" % (program))))
            return

        for a in actors:
            if a not in self.actors:
                cmd.warn("permsTxt=%s" % (CPL.qstr("Actor %s is not subject to permissions." % (a))))
            else:
                d[a] = True

        self.genAuthKeys(programs=[program], cmd=cmd)
        
    def dropActorsFromProgram(self, program, actors, cmd=None):
        """ Remove a list of actors to a commander's authorized list.
        """

        if self.debug > 3:
            CPL.log("auth.dropActors", "dropping actors for program %s: %s" % (program, actors))
            
        try:
            d = self.programs[program]
        except KeyError, e:
            cmd.fail("permsTxt=%s" % (CPL.qstr("Program %s did not have an authorization entry, so could not be modified" % (program))))
            return

        for a in actors:
            try:
                del d[a]
            except KeyError:
                cmd.warn("permsTxt=%s" % (CPL.qstr("Actor %s was not in program %s's athorized list" % (a, program))))

        self.genAuthKeys(programs=[program], cmd=cmd)

if __name__ == "__main__":
    def checkAndPrint(cmdr, actor, expect):
        access = a.checkAccess(cmdr, actor)
        if access == expect:
            ok = "    "
        else:
            ok = "BAD "
            
        print "%s %s\t-> %s\t = %s" % (ok, cmdr, actor, access)
        
    g.actors = ('tcc', 'them')
    a = Auth(CPL.tcmd(name='auth'), debug=9)

    a.status()

    checkAndPrint("meme", "them", False)

    a.addPrograms(['me'], ['yy'])
    checkAndPrint("meme", "them", False)
    checkAndPrint("me.me", "them", False)

    #a.addActors('xxxx', 'yyyy')
    a.addActors('me.me', ['them', 'theOthers'])
    checkAndPrint("me.me", "them", True)
    checkAndPrint("me.me", "theOthers", True)
    checkAndPrint("me.me", "theOtherOtherss", False)

    a.addActors('me.me', ['them'])
    checkAndPrint("me.me", "them", True)

    a.status()
    
    a.lockActors(['vvv', 'them'])
    checkAndPrint("me.me", "them", False)

    a.addPrograms(['too'], ['them'])

    a.status()

    a.unlockActors(['them'])
    checkAndPrint("me.me", "them", True)

    a.unlockActors(['them'])
    checkAndPrint("me.me", "them", True)

    a.unlockActors(['vvv'])
    checkAndPrint("me.me", "them", True)

    a.status()

    a.dropActors('me.me', ['them'])
    checkAndPrint("me.me", "them", False)
    checkAndPrint("me.me", "theOthers", True)

    a.dropPrograms([])
    checkAndPrint("me.me", "theOthers", False)

    a.status()

