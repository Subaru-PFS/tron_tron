#!/usr/local/bin/python
"""Basic framework for a hub actor or ICC based on the Tcl event loop.

Properties:
- Multiple users may connect.
- Only one user command may be executing at a time (though a new command may supersede
  an existing command if the existing command specifically permits it).
- Command format is:
    [cmdId[ msgId]][cmdVerb[ cmdArgs]]
  where [] indicates an optional element.
  Note: msgId is ignored and is only permitted to make the hub happy.
- Command verbs are case-insensitive and must:
  - Start with a letter or underscore
  - Contain only letters, numbers or underscores
"""
__all__ = ["Actor"]

import sys
import traceback
#import RO.AddCallback
import RO.SeqUtil
from RO.StringUtil import quoteStr
import RO.Comm.TkSocket

import Command


class Actor(object):
    """Base class for a hub actor or instrument control computer using the Tcl event loop.
    
    Subclass this and add cmd_ methods to add commands, (or add commands by adding items to self.locCmdDict
    but be careful with command names -- see comment below)
    
    Inputs:
    - userPort      port on which to listen for users
    - devs          one or more Device objects that this ICC controls; None if none
    - maxUsers      the maximum allowed # of users (if None then no limit)
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
        
        self.devNameDict = {} # dev name: dev
        self.devConnDict = {} # dev conn: dev
        self.devCmdDict = {} # dev verb: dev
        for dev in devs:
            self.devNameDict[dev.name] = dev
            self.devConnDict[dev.conn] = dev
            dev.writeToUsers = self.writeToUsers
            dev.conn.addStateCallback(self.devConnStateCallback)
            for cmdVerb in dev.cmds:
                self.devCmdDict[cmdVerb] = dev
        
        # local command dictionary containing cmd verb: method
        # all methods whose name starts with cmd_ are added
        # each such method must accept one argument: a UserCmd
        self.locCmdDict = dict()
        for attrName in dir(self):
            if attrName.startswith("cmd_"):
                cmdVerb = attrName[4:].lower()
                self.locCmdDict[cmdVerb] = getattr(self, attrName)
        
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
        if newCmd.cmdArgs:
            raise RuntimeError("%s takes no arguments" % (newCmd.cmdVerb,))
    
    def checkLocalCmd(self, newCmd):
        """Check if the new local command can run given what else is going on.
        If not then raise TclActor.ConflictError with a reason.
        If it can run but an existing command must be superseded then supersede the old command here.
        
        Note that each cmd_foo method can perform additional checks and cancellation.

        Subclasses will typically want to override this method.
        """
        pass
    
    def cmdDone(self, cmd):
        """Report command completion or failure"""
        is not cmd.isDone():
            return
        msgCode = cmd.getMsgCode()
        msgStr = "Text=%s" % (quoteStr(cmd.reason)) if cmd.reason else ""
        self.writeToUsers(cmd.cmdID, cmd.userID, msgCode, msgStr)
    
    def devConnStateCallback(self, devConn):
        """Called when a device's connection state changes."""
        dev = self.devConnDict[devConn]
        wantConn, cmd = dev.connReq
        if cmd == None:
            cmd = NullCmd
        isDone, isOK, state, stateStr, reason = devConn.getProgress(wantConn)
        
        # output changed state
        quotedReason = quoteStr(reason)
        msgCode = "i" if isOK else "w"
        self.writeToUsers(cmd.cmdID, cmd.userID, msgCode, "%sConnState = %r, %s" % (dev.name, stateStr, quotedReason))
        
        # if user command has finished then mark it as such and clear device state callback
        if cmd.userID != 0 and isDone:
            cmdState = "done" if isOK else "failed"
            cmd.setState(cmdState, reason)
            dev.connReq = (wantConn, NullCmd)
    
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
        
        currIDs = self.userDict.values()
        userID = 1
        while userID in currIDs:
            userID += 1
        
        self.userDict[tkSock] = userID
        tkSock.setReadCallback(self.newCmd)
        tkSock.setStateCallback(self.userStateChanged)
        
        self.cmd_users(Command.UserCmd(userID=userID))
        
    def newCmd(self, tkSock):
        """Called when a command is read from a user.
        """
        cmdStr = tkSock.readLine()
        if not cmdStr:
            return
        userID = self.userDict[tkSock]
        
        try:
            cmd = Command.UserCmd(userID, cmdStr, self.cmdDone)
        except RuntimeError:
            self.writeToUsers(0, userID, "f", "CannotParse=" + quoteStr(cmdStr))
            return

        #print "read cmd=%r cmdID=%s; locID=%s" % (cmd.cmdStr, cmd.cmdID, cmd.locID)
        
        if not cmd.cmdVerb:
            # echo to show alive
            self.writeToOneUser(cmdID, userID, ":")
            return
        
        cmdFunc = self.locCmdDict.get(cmd.cmdVerb)
        if cmdFunc != None:
            # execute local command
            try:
                checkLocalCmd(cmd)
                cmdFunc(cmd)
            except TclActor.ConflictError, e:
                cmd.setState("failed", str(e))
                return
            except Exception, e:
                sys.stderr.write("cmd %r failed\n" % cmdStr)
                sys.stderr.write("function %s raised %s\n" % (cmdFunc, e))
                traceback.print_exc(file=sys.stderr)
                quotedErr = quoteStr(str(e))
                self.writeToUsers(cmd.cmdID, cmd.userID, "f", "Exception=%s; Text=%s" % (e.__class__.__name__, quotedErr))
            return
        
        dev = self.devCmdDict.get(cmd.cmdVerb)
        if dev != None:
            # execute known device command
            dev.sendCmd(cmd)
            return
        
        dev = self.devNameDict.get(cmd.cmdVerb)
        if dev != None:
            # command verb is the name of a device
            # the rest of the text gets sent to the device
            cmd.cmdStr = cmd.cmdArgs
            dev.sendCmd(cmd)
            return

        self.writeToUsers(cmd.cmdID, cmd.userID, "f", "UnknownCommand=%s" % (cmd.cmdVerb,))
        
    def userStateChanged(self, tkSock):
        """Called when a user connection changes state.
        """
        if not tkSock.isClosed():
            return

        try:
            del self.userDict[tkSock]
        except KeyError:
            sys.stderr.write("ICC warning: user socket closed but could not find in userDict")

    def formatUserOutput(self, cmdID, userID, msgCode, msgStr):
        """Format a string to send to the all users.
        """
        return "%d %d %s %s" % (cmdID, userID, msgCode, msgStr)
    
    def getUserSock(self, userID):
        """Get a user socket given the user ID number.
        Raise KeyError if user unknown.
        """
        for sock, sockUserID in self.userDict.iteritems():
            if sockUserID == userID:
                return sock
        raise KeyError("No user with id %s" % (userID,))

    def writeToUsers(self, cmdID, userID, msgCode, msgStr):
        """Write a message to all users.
        """
        fullMsgStr = self.formatUserOutput(cmdID, userID, msgCode, msgStr)
        for sock, sockUserID in self.userDict.iteritems():
            sock.writeLine(fullMsgStr)
    
    def writeToOneUser(self, cmdID, userID, msgCode, msgStr=""):
        """Write a message to one user.
        """
        sock = self.getUserSock(userID)
        fullMsgStr = self.formatUserOutput(cmdID, userID, msgCode, msgStr)
        sock.writeLine(fullMsgStr)
    
    def cmd_connDev(self, cmd=NullCmd):
        """Connect or reconnect one or more devices.
        Command args: 0 or more device names, space-separated
        """
        if cmd.cmdArgs:
            devNameList = cmd.cmdArgs.split()
        else:
            devNameList = self.devNameDict.keys()
        
        for devName in devNameList:
            dev = self.devNameDict[devName]
            dev.conn.connect()
            dev.connReq = (True, cmd)
    
    def cmd_disconnDev(self, cmd=NullCmd):
        """Disconnect one or more devices.
        Command args: 0 or more device names, space-separated
        """
        if cmd.cmdArgs:
            devNameList = cmd.cmdArgs.split()
        else:
            devNameList = self.devNameDict.keys()
        
        for devName in devNameList:
            dev = self.devNameDict[devName]
            dev.conn.disconnect()
            dev.connReq = (False, cmd)
    
    def cmd_exit(self, cmd=NullCmd):
        """Log off the user"""
        self.cmd_quit(cmd)
    
    def cmd_quit(self, cmd=NullCmd):
        """Log off the user"""
        sock = self.getUserSock(cmd.userID)
        sock.close()
    
    def cmd_users(self, cmd=NullCmd):
        """Show user information"""
        numUsers = len(self.userDict)
        for sock, userID in self.userDict.iteritems():
            msgStr = self.formatUserOutput(cmd.cmdID, cmd.userID, "i",
                "NumUsers=%d, YourUserID=%d" % (numUsers, userID))
            sock.writeLine(msgStr)


if __name__ == "__main__":
    import Tkinter
    root = Tkinter.Tk()
    b = TclActor(
        userPort = 2005,
    )
    print b.locCmdDict
