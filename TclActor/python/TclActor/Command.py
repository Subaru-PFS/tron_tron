#!/usr/local/bin/python
"""Command objects for the Tcl Actor
"""
__all__ = ["BaseCmd", "DevCmd", "UserCmd", "NullCmd"]

import re
#import sys
import RO.AddCallback

class BaseCmd(RO.AddCallback.BaseMixin):
    """Base class for commands of all types (user and device).
    """
    # state constants
    DoneStates = set(("done", "cancelled", "failed"))
    StateSet = DoneStates | set(("ready", "running", "cancelling", "failing"))
    def __init__(self, cmdStr, callFunc = None, timeLimit = None):
        self.cmdStr = cmdStr
        self.state = "ready"
        self.reason = ""
        self.callFunc = callFunc
        self.timeLimit = timeLimit
        self.cmdToTrack = None
        RO.AddCallback.BaseMixin.__init__(self, callFunc)
    
    def isDone(self):
        return self.state in self.DoneStates

    def getState(self):
        """Return state and a reason for that state"""
        return (self.state, self.reason)
    
    def setState(self, newState, reason=""):
        """Set the state of the command and (if new state is done) remove all callbacks.

        If the new state is Failed then please supply a reason.
        
        Error conditions:
        - Raise RuntimeError if this command is finished.
        """
        if self.isDone():
            raise RuntimeError("Command is done; cannot change state")
        if newState not in self.StateSet:
            raise RuntimeError("Unknown state %s" % newState)
        self.state = newState
        self.reason = reason
        self._basicDoCallbacks(self)
        if self.isDone():
            self._removeAllCallbacks()
            self.cmdToTrack = None
    
    def trackCmd(self, cmdToTrack):
        """Tie the state of this command to another command"""
        if self.isDone():
            raise RuntimeError("Finished; cannot track a command")
        if self.cmdToTrack:
            raise RuntimeError("Already tracking a command")
        cmdToTrack.addCallback(self.trackUpdate)
        self.cmdToTrack = cmdToTrack
    
    def trackUpdate(self, cmdToTrack):
        """Tracked command's state has changed"""
        state, reason = cmdToTrack.getState()
        self.setState(state, reason)
    
    def untrackCmd(self):
        """Stop tracking a command if tracking one, else do nothing"""
        if self.cmdToTrack:
            self.cmdToTrack.removeCallback(self.trackUpdate)
            self.cmdToTrack = None        

class DevCmd(BaseCmd):
    """Generic device command that assumes all commands have the format "[cmdId] verb arguments"
    
    If you are talking to a device with different rules then please make your own subclass of BaseCmd.
    """
    _DevCmdRE = re.compile(r"((?P<cmdID>\d+)(?:\s+)?\s+)?((?P<cmdVerb>[A-Za-z_]\w*)(\s+(?P<cmdArgs>.*))?)?")
    def __init__(self,
        cmdStr = "",
        callFunc = None,
    ):
        BaseCmd.__init__(self, cmdStr, callFunc=callFunc)
        self.parseCmdStr(cmdStr)
    
    def parseCmdStr(self, cmdStr):
        """Parse a user command string and set cmdID, cmdVerb and cmdArgs.
        
        Inputs:
        - cmdStr: command string (see module doc string for format)
        """
        cmdMatch = self._DevCmdRE.match(cmdStr)
        if not cmdMatch:
            raise RuntimeError("Could not parse command %r" % cmdStr)
        
        cmdDict = cmdMatch.groupdict("")
        cmdIDStr = cmdDict["cmdID"]
        self.cmdID = int(cmdIDStr) if cmdIDStr else 0
        self.cmdVerb = cmdDict["cmdVerb"]
        self.cmdArgs = cmdDict["cmdArgs"]

class UserCmd(BaseCmd):
    """A command from a user (typically the hub)
    
    Inputs:
    - userID    ID of user (always 0 if a single-user actor)
    - cmdStr    full command
    - callFunc  function to call when command finishes or fails;
                the function receives two arguments: this UserCmd, isOK
    Attributes:
    - cmdVerb   command verb in lowercase
    - cmdArgs   command arguments (in original case)
    """
    _MsgCodeDict = dict(
        ready = "i",
        running = "i",
        cancelling = "w",
        failing = "w",
        cancelled = "f",
        failed = "f",
        done = ":",
    )
    _UserCmdRE = re.compile(r"((?P<cmdID>\d+)(?:\s+\d+)?\s+)?((?P<cmdVerb>[A-Za-z_]\w*)(\s+(?P<cmdArgs>.*))?)?")
    def __init__(self,
        userID = 0,
        cmdStr = "",
        callFunc = None,
    ):
        self.userID = userID
        BaseCmd.__init__(self, cmdStr, callFunc=callFunc)
        self.parseCmdStr(cmdStr)
    
    def parseCmdStr(self, cmdStr):
        """Parse a user command string and set cmdID, cmdVerb and cmdArgs.
        
        Inputs:
        - cmdStr: command string (see module doc string for format)
        """
        cmdMatch = self._UserCmdRE.match(cmdStr)
        if not cmdMatch:
            raise RuntimeError("Could not parse command %r" % cmdStr)
        
        cmdDict = cmdMatch.groupdict("")
        cmdIDStr = cmdDict["cmdID"]
        self.cmdID = int(cmdIDStr) if cmdIDStr else 0
        self.cmdVerb = cmdDict["cmdVerb"].lower()
        self.cmdArgs = cmdDict["cmdArgs"]
    
    def getMsgCode(self):
        """Return the hub message code appropriate to the current state"""
        return self._MsgCodeDict[self.state]

        
NullCmd = UserCmd()
