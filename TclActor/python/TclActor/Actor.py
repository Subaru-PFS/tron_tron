#!/usr/local/bin/python
"""Basic framework for a hub actor or ICC based on the Tcl event loop.
"""
__all__ = ["Actor", "ConflictError"]

import sys
import traceback
#import RO.AddCallback
import RO.SeqUtil
from RO.StringUtil import quoteStr
import RO.Comm.TkSocket

import Command

class ConflictError(Exception):
    pass


class Actor(object):
    """Base class for a hub actor or instrument control computer using the Tcl event loop.
    
    Subclass this and add cmd_ methods to add commands, (or add commands by adding items to self.locCmdDict
    but be careful with command names -- see comment below)
    
    Inputs:
    - userPort      port on which to listen for users
    - devs          one or more Device objects that this ICC controls; None if none
    - maxUsers      the maximum allowed # of users (if None then no limit)
    
    Commands are defined in three ways:
    - Local commands: all Actor methods whose name starts with "cmd_";
        the rest of the name is the command verb
    - Device commands: commands specified via argument cmdInfo when creating the device;
        these commands are sent directly to the device that claims to handle them
        (with a new unique command ID number if the device can execute multiple commands at once).
    - Direct device access commands (for debugging and engineering): the command verb is the device name
        and the subsequent text is sent directly to the device
    
    Error conditions:
    - Raise RuntimeError if there is any command verbs is defined more than once.
    """
    def __init__(self,
        userPort,
        devs = None,
        maxUsers = None,
    ):
        self.maxUsers = maxUsers
        if devs == None:
            devs = ()
        else:
            devs = RO.SeqUtil.asList(devs)
        
        # local command dictionary containing cmd verb: method
        # all methods whose name starts with cmd_ are added
        # each such method must accept one argument: a UserCmd
        self.locCmdDict = dict()
        for attrName in dir(self):
            if attrName.startswith("cmd_"):
                cmdVerb = attrName[4:].lower()
                self.locCmdDict[cmdVerb] = getattr(self, attrName)
        
        cmdVerbSet = set(self.locCmdDict.keys())
        cmdCollisionSet = set()
        
        self.devNameDict = {} # dev name: dev
        self.devConnDict = {} # dev conn: dev
        self.devCmdDict = {} # dev command verb: (dev, cmdHelp)
        for dev in devs:
            self.devNameDict[dev.name] = dev
            self.devConnDict[dev.conn] = dev
            dev.writeToUsers = self.writeToUsers
            dev.conn.addStateCallback(self.devConnStateCallback)
            for cmdVerb, devCmdVerb, cmdHelp in dev.cmdInfo:
                devCmdVerb = devCmdVerb or cmdVerb
                self.devCmdDict[cmdVerb] = (dev, devCmdVerb, cmdHelp)
            newCmdSet = set(self.devCmdDict.keys())
            cmdCollisionSet.update(cmdVerbSet & newCmdSet)
            cmdVerbSet.update(newCmdSet)
        
        newCmdSet = set(self.devNameDict.keys())
        cmdCollisionSet.update(cmdVerbSet & newCmdSet)
        cmdVerbSet.update(newCmdSet)
        if cmdCollisionSet:
            raise RuntimeError("Multiply defined commands: %s" %  ", ".join(cmdCollisionSet))
        
        # entries are: user's socket: userID
        self.userDict = dict()
        
        self.userListener = RO.Comm.TkSocket.TkServerSocket(
            connCallback = self.newUser,
            port = userPort,
            binary = False,
        )
        
        # connect all devices
        self.initialConn()
    
    def checkNoArgs(self, newCmd):
        """Raise RuntimeError if newCmd has arguments"""
        if newCmd and newCmd.cmdArgs:
            raise RuntimeError("%s takes no arguments" % (newCmd.cmdVerb,))
    
    def checkLocalCmd(self, newCmd):
        """Check if the new local command can run given what else is going on.
        If not then raise TclActor.ConflictError(textMsg)
        If it can run but an existing command must be superseded then supersede the old command here.
        
        Note that each cmd_foo method can perform additional checks and cancellation.

        Subclasses will typically want to override this method.
        """
        pass
    
    def cmdCallback(self, cmd):
        """Called when a command changes state; report completion or failure"""
        if not cmd.isDone():
            return
        msgCode, msgStr = cmd.hubFormat()
        self.writeToUsers(msgCode, msgStr, cmd=cmd)
    
    def devConnStateCallback(self, devConn):
        """Called when a device's connection state changes."""
        dev = self.devConnDict[devConn]
        wantConn, cmd = dev.connReq
        isDone, isOK, state, stateStr, reason = devConn.getProgress(wantConn)
        
        # output changed state
        quotedReason = quoteStr(reason)
        msgCode = "i" if isOK else "w"
        msgStr = "%sConnState = %r, %s" % (dev.name, stateStr, quotedReason)
        self.writeToUsers(msgCode, msgStr, cmd=cmd)
        
        # if user command has finished then mark it as such and clear device state callback
        if cmd and isDone:
            cmdState = "done" if isOK else "failed"
            cmd.setState(cmdState, reason)
            dev.connReq = (wantConn, None)
    
    def initialConn(self):
        """Perform initial connections.
        Normally this just calls cmd_connDev,
        but you can override this command if you need a special startup sequence
        such as waiting until devices boot up.
        """
        self.cmd_connDev()
    
    def newUser(self, tkSock):
        """A new user has connected.
        Assign an ID and report it to the user.
        """
        if self.maxUsers != None:
            if len(self.userDict) >= self.maxUsers:
                tkSock.writeLine("0 0 E NoFreeConnections")
                tkSock.close()
                return
        
        currIDs = set(self.userDict.values())
        userID = 1
        while userID in currIDs:
            userID += 1
        
        self.userDict[tkSock] = userID
        tkSock.setReadCallback(self.newCmd)
        tkSock.setStateCallback(self.userStateChanged)
        
        # report user information and additional info
        self.cmd_users(Command.UserCmd(userID=userID))
    
    def newUserOutput(self, userID, tkSock):
        """Override to report status to the new user (other than userID)"""
        pass
        
    def newCmd(self, tkSock):
        """Called when a command is read from a user.
        
        Note: command name collisions are resolved as follows:
        - local commands (cmd_<foo> methods of this actor)
        - commands handled by devices
        - direct device access commands (device name)
        """
        cmdStr = tkSock.readLine()
        if not cmdStr:
            return
        userID = self.userDict[tkSock]
        
        try:
            cmd = Command.UserCmd(userID, cmdStr, self.cmdCallback)
        except RuntimeError:
            self.writeToOneUser("f", "CannotParse=" + quoteStr(cmdStr), userID=userID)
            return

        #print "newCmd: userID=%s; cmdID=%s; cmdVerb=%r; cmdArgs=%r" % (cmd.userID, cmd.cmdID, cmd.cmdVerb, cmd.cmdArgs)
        
        if not cmd.cmdVerb:
            # echo to show alive
            self.writeToOneUser(":", "", cmd=cmd)
            return
        
        cmdFunc = self.locCmdDict.get(cmd.cmdVerb)
        if cmdFunc != None:
            # execute local command
            try:
                #print "newCmd: checking local function %s" % (cmdFunc,)
                self.checkLocalCmd(cmd)
                #print "newCmd: executing local function %s" % (cmdFunc,)
                cmdFunc(cmd)
            except ConflictError, e:
                #print "newCmd: command rejected due to conflict"
                cmd.setState("failed", str(e))
                return
            except Exception, e:
                sys.stderr.write("command %r failed\n" % (cmdStr,))
                sys.stderr.write("function %s raised %s\n" % (cmdFunc, e))
                traceback.print_exc(file=sys.stderr)
                quotedErr = quoteStr(str(e))
                msgStr = "Exception=%s; Text=%s" % (e.__class__.__name__, quotedErr)
                self.writeToUsers("f", msgStr, cmd=cmd)
            return
        
        devCmdInfo = self.devCmdDict.get(cmd.cmdVerb)
        print "devCmdInfo=", devCmdInfo
        if devCmdInfo:
            # execute device command
            dev, devCmdVerb, cmdHelp = devCmdInfo
            devCmd = Command.DevCmd("%s %s" % (devCmdVerb, cmd.cmdArgs), userCmd=cmd)
            dev.newCmd(devCmd)
            return
        
        dev = self.devNameDict.get(cmd.cmdVerb)
        if dev != None:
            # command verb is the name of a device
            # the rest of the text gets sent to the device
            cmd.cmdStr = cmd.cmdArgs
            dev.sendCmd(cmd)
            return

        self.writeToOneUser("f", "UnknownCommand=%s" % (cmd.cmdVerb,), cmd=cmd)
        
    def userStateChanged(self, tkSock):
        """Called when a user connection changes state.
        """
        if not tkSock.isClosed():
            return

        try:
            del self.userDict[tkSock]
        except KeyError:
            sys.stderr.write("ICC warning: user socket closed but could not find in userDict")
    
    def getUserCmdID(self, cmd=None, userID=None, cmdID=None):
        """Return userID, cmdID based on user-supplied information.
        
        Each item is 0 is: <item> if <item> != None, else cmd.<item> if cmd != None else 0
        """
        return (
            userID if userID != None else (cmd.userID if cmd else 0),
            cmdID if cmdID != None else (cmd.cmdID if cmd else 0),
        )

    def formatUserOutput(self, msgCode, msgStr, userID=None, cmdID=None):
        """Format a string to send to the all users.
        """
        return "%d %d %s %s" % (userID, cmdID, msgCode, msgStr)
    
    def getUserSock(self, userID):
        """Get a user socket given the user ID number.
        Raise KeyError if user unknown.
        """
        for sock, sockUserID in self.userDict.iteritems():
            if sockUserID == userID:
                return sock
        raise KeyError("No user with id %s" % (userID,))

    def writeToUsers(self, msgCode, msgStr, cmd=None, userID=None, cmdID=None):
        """Write a message to all users.
        
        cmdID and userID are obtained from cmd unless overridden by the explicit argument. Both default to 0.
        """
        userID, cmdID = self.getUserCmdID(cmd=cmd, userID=userID, cmdID=cmdID)
        fullMsgStr = self.formatUserOutput(msgCode, msgStr, userID=userID, cmdID=cmdID)
        #print "writeToUsers(%s)" % (fullMsgStr,)
        for sock, sockUserID in self.userDict.iteritems():
            sock.writeLine(fullMsgStr)
    
    def writeToOneUser(self, msgCode, msgStr, cmd=None, userID=None, cmdID=None):
        """Write a message to one user.

        cmdID and userID are obtained from cmd unless overridden by the explicit argument. Both default to 0.
        """
        userID, cmdID = self.getUserCmdID(cmd=cmd, userID=userID, cmdID=cmdID)
        if userID == 0:
            raise RuntimeError("Cannot write to user 0")
        sock = self.getUserSock(userID)
        fullMsgStr = self.formatUserOutput(msgCode, msgStr, userID=userID, cmdID=cmdID)
        #print "writeToOneUser(%s)" % (fullMsgStr,)
        sock.writeLine(fullMsgStr)
    
    def cmd_connDev(self, cmd=None):
        """[dev1 [dev2 [...]]]: connect or reconnect one or more devices (all if none specified).
        Command args: 0 or more device names, space-separated
        """
        if cmd and cmd.cmdArgs:
            devNameList = cmd.cmdArgs.split()
        else:
            devNameList = self.devNameDict.keys()
        
        for devName in devNameList:
            dev = self.devNameDict[devName]
            dev.conn.connect()
            dev.connReq = (True, cmd)
    
    def cmd_disconnDev(self, cmd=None):
        """[dev1 [dev2 [...]]]: disconnect one or more devices (all if none specified).
        Command args: 0 or more device names, space-separated
        """
        if cmd and cmd.cmdArgs:
            devNameList = cmd.cmdArgs.split()
        else:
            devNameList = self.devNameDict.keys()
        
        for devName in devNameList:
            dev = self.devNameDict[devName]
            dev.conn.disconnect()
            dev.connReq = (False, cmd)
    
    def cmd_exit(self, cmd=None):
        """disconnect yourself"""
        sock = self.getUserSock(cmd.userID)
        sock.close()
    
    def cmd_help(self, cmd=None):
        """print this help"""
        helpList = []
        
        # commands handled by this actor
        for cmdVerb, cmdFunc in self.locCmdDict.iteritems():
            helpStr = cmdFunc.__doc__.split("\n")[0]
            if ":" in helpStr:
                joinStr = " "
            else:
                joinStr = ": "
            helpList.append(joinStr.join((cmdVerb, helpStr)))
        
        # commands handled by a device
        for cmdVerb, cmdInfo in self.devCmdDict.iteritems():
            helpStr = cmdInfo[2]
            if ":" in helpStr:
                joinStr = " "
            else:
                joinStr = ": "
            helpList.append(joinStr.join((cmdVerb, helpStr)))

        helpList.sort()
        
        # direct device access commands (these go at the end)
        helpList += ["", "Direct device access commands:"]
        for devName, dev in self.devNameDict.iteritems():
            helpList.append("%s <text>: send <text> to device %s" % (devName, devName))
        
        for helpStr in helpList:
            self.writeToUsers("i", "Text=%r" % (helpStr,), cmd=cmd)
    
    def cmd_users(self, cmd):
        """show user information including your userID
        The command is required.
        """
        numUsers = len(self.userDict)
        if numUsers == 0:
            return
        msgData = [
            "YourUserID=%s" % (cmd.userID,),
            "NumUsers=%s" % (numUsers,),
        ]
        userDict = dict() # dict of userID, addr
        sockList = self.userDict.keys()
        userIDList = self.userDict.values()
        userSockList = sorted(zip(userIDList, sockList))
        userInfo = []
        for userID, sock in userSockList:
            userInfo += [str(userID), sock._addr]
        userInfoStr = ",".join(userInfo)
        msgData.append("UserInfo=%s" % (userInfoStr,))
        msgStr = "; ".join(msgData)
        msgStr = self.writeToOneUser("i", msgStr, cmd=cmd)


if __name__ == "__main__":
    import Tkinter
    root = Tkinter.Tk()
    b = TclActor(
        userPort = 2005,
    )
    print b.locCmdDict
