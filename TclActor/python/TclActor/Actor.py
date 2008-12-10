"""Basic framework for a hub actor or ICC based on the Tcl event loop.
"""
__all__ = ["Actor"]

import operator
import sys
import types
import traceback
import RO.Comm.TkSocket
import RO.SeqUtil
from RO.StringUtil import quoteStr
import Command


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
        the rest of the name is the command verb.
        These methods must return True if the command is executed in the background
        (otherwise they will be reported as "done" when the method ends)
    - Device commands: commands specified via argument cmdInfo when creating the device;
        these commands are sent directly to the device that claims to handle them
        (with a new unique command ID number if the device can execute multiple commands at once).
        The device must finish the command (unless dev.newCmd raises an exception).
    - Direct device access commands (for debugging and engineering): the command verb is the device name
        and the subsequent text is sent directly to the device.
        The device must finish the command (unless dev.newCmd raises an exception).
    
    Error conditions:
    - Raise RuntimeError if there is any command verbs is defined more than once.
    """
    def __init__(self,
        userPort,
        devs = None,
        maxUsers = None,
    ):
        self.maxUsers = maxUsers
        # entries are: user's socket: userID
        self.userDict = dict()

        if devs == None:
            devs = ()
        else:
            devs = RO.SeqUtil.asList(devs)
        self.doDebugMsgs = False
        
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
        
        self.userListener = RO.Comm.TkSocket.TkServerSocket(
            connCallback = self.newUser,
            port = userPort,
            binary = False,
        )
        
        # connect all devices
        self.initialConn()
    
    def checkNoArgs(self, newCmd):
        """Raise Command.CommandError if newCmd has arguments"""
        if newCmd and newCmd.cmdArgs:
            raise Command.CommandError("%s takes no arguments" % (newCmd.cmdVerb,))
    
    def checkLocalCmd(self, newCmd):
        """Check if the new local command can run given what else is going on.
        If not then raise Command.CommandError(textMsg)
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
        self.showOneDevConnStatus(dev, cmd=cmd)
        state, stateStr, reason = devConn.getFullState()
        if cmd and devConn.isDone():
            succeeded = bool(wantConn) == devConn.isConnected()
            #cmdState = "done" if succeeded else "failed"
            if succeeded:
                cmdState = "done" 
            else:
                cmdState = "failed" 
            cmd.setState(cmdState, textMsg=reason)
            dev.connReq = (wantConn, None)

    def formatUserOutput(self, msgCode, msgStr, userID=None, cmdID=None):
        """Format a string to send to the all users.
        """
        return "%d %d %s %s" % (userID, cmdID, msgCode, msgStr)
    
    def getUserCmdID(self, cmd=None, userID=None, cmdID=None):
        """Return userID, cmdID based on user-supplied information.
        
        Each item is 0 is: <item> if <item> != None, else cmd.<item> if cmd != None else 0
        """
        if userID == None:
            userID = 0
            if cmd:
                userID = cmd.userID

        if cmdID == None:
            cmdID = 0
            if cmd:
                cmdID = cmd.cmdID
            
        #return (
        #    userID if userID != None else (cmd.userID if cmd else 0),
        #    cmdID if cmdID != None else (cmd.cmdID if cmd else 0),
        #)
        return userID, cmdID
    
    def getUserSock(self, userID):
        """Get a user socket given the user ID number.
        Raise KeyError if user unknown.
        """
        for sock, sockUserID in self.userDict.iteritems():
            if sockUserID == userID:
                return sock
        raise KeyError("No user with id %s" % (userID,))
    
    def initialConn(self):
        """Perform initial connections.
        Normally this just calls cmd_connDev,
        but you can override this command if you need a special startup sequence
        such as waiting until devices boot up.
        """
        self.cmd_connDev()
    
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
        
        cmd = Command.UserCmd(userID, cmdStr, self.cmdCallback)

        #print "newCmd: userID=%s; cmdID=%s; cmdVerb=%r; cmdArgs=%r" % (cmd.userID, cmd.cmdID, cmd.cmdVerb, cmd.cmdArgs)
        
        if not cmd.cmdVerb:
            # echo to show alive
            self.writeToOneUser(":", "", cmd=cmd)
            return
        
        # see if command is a local command
        cmdFunc = self.locCmdDict.get(cmd.cmdVerb)
        if cmdFunc != None:
            # execute local command
            try:
                self.checkLocalCmd(cmd)
                retVal = cmdFunc(cmd)
            except Command.CommandError, e:
                cmd.setState("failed", str(e))
                return
            except Exception, e:
                sys.stderr.write("command %r failed\n" % (cmdStr,))
                sys.stderr.write("function %s raised %s\n" % (cmdFunc, e))
                traceback.print_exc(file=sys.stderr)
                quotedErr = quoteStr(str(e))
                msgStr = "Exception=%s; Text=%s" % (e.__class__.__name__, quotedErr)
                self.writeToUsers("f", msgStr, cmd=cmd)
            else:
                if not retVal and not cmd.isDone():
                    cmd.setState("done")
            return
        
        # see if command is a device command
        dev = None
        devCmdStr = ""
        devCmdInfo = self.devCmdDict.get(cmd.cmdVerb)
        if devCmdInfo:
            # command verb is one handled by a device
            dev, devCmdVerb, cmdHelp = devCmdInfo
            devCmdStr = "%s %s" % (devCmdVerb, cmd.cmdArgs)
        else:
            dev = self.devNameDict.get(cmd.cmdVerb)
            if dev != None:
                # command verb is the name of a device;
                # the command arguments are the string to send to the device
                devCmdStr = cmd.cmdArgs
        if dev and devCmdStr:
            try:
                dev.newCmd(devCmdStr, userCmd=cmd)
            except Command.CommandError, e:
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

        self.writeToOneUser("f", "UnknownCommand=%s" % (cmd.cmdVerb,), cmd=cmd)

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
        fakeCmd = Command.UserCmd(userID=userID)
        self.showUserInfo(fakeCmd)
        self.showDevConnStatus(cmd=fakeCmd, onlyOneUser=True, onlyIfNotConn=True)
        self.newUserOutput(userID)
    
    def newUserOutput(self, userID):
        """Override to report additional status to the new user
        other than userID and bad device status
        """
        pass

    def showDevConnStatus(self, cmd=None, onlyOneUser=False, onlyIfNotConn=False):
        """Show connection status for all devices"""
        for devName in sorted(self.devNameDict.keys()):
            dev = self.devNameDict[devName]
            self.showOneDevConnStatus(dev, onlyOneUser=onlyOneUser, onlyIfNotConn=onlyIfNotConn, cmd=cmd)
    
    def showOneDevConnStatus(self, dev, cmd=None, onlyOneUser=False, onlyIfNotConn=False):
        """Show connection status for one device"""
        if onlyIfNotConn and dev.conn.isConnected():
            return

        state, stateStr, reason = dev.conn.getFullState()
        quotedReason = quoteStr(reason)
        #msgCode = "i" if dev.conn.isConnected() else "w"
        if dev.conn.isConnected():
            msgCode = "i" 
        else:
            msgCode = "w"
        msgStr = "%sConnState = %r, %s" % (dev.name, stateStr, quotedReason)
        if onlyOneUser:
            self.writeToOneUser(msgCode, msgStr, cmd=cmd)
        else:
            self.writeToUsers(msgCode, msgStr, cmd=cmd)

    def showUserInfo(self, cmd):
        """Show user information including your userID.
        The command is required.
        """
        numUsers = len(self.userDict)
        if numUsers == 0:
            return
        msgData = [
            "YourUserID=%s" % (cmd.userID,),
            "NumUsers=%s" % (numUsers,),
        ]
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
        
    def userStateChanged(self, tkSock):
        """Called when a user connection changes state.
        """
        if not tkSock.isClosed():
            return

        try:
            del self.userDict[tkSock]
        except KeyError:
            sys.stderr.write("ICC warning: user socket closed but could not find in userDict")

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
        sock.writeLine(fullMsgStr)
    
    def cmd_connDev(self, cmd=None):
        """[dev1 [dev2 [...]]]: connect one or more devices (all devices if none specified).
        Already-connected devices are ignored (except to output status).
        Command args: 0 or more device names, space-separated
        """
        if cmd and cmd.cmdArgs:
            devNameList = cmd.cmdArgs.split()
        else:
            devNameList = self.devNameDict.keys()
        
        runInBackground = False
        for devName in devNameList:
            dev = self.devNameDict[devName]
            if dev.conn.isConnected():
                self.showOneDevConnStatus(dev, cmd=cmd)
            else:
                runInBackground = True
                dev.connReq = (True, cmd)
                dev.conn.connect()
        return runInBackground
    
    def cmd_disconnDev(self, cmd=None):
        """[dev1 [dev2 [...]]]: disconnect one or more devices (all if none specified).
        Already-disconnected devices are ignored (except to output status).
        Command args: 0 or more device names, space-separated
        """
        if cmd and cmd.cmdArgs:
            devNameList = cmd.cmdArgs.split()
        else:
            devNameList = self.devNameDict.keys()
        
        runInBackground = False
        for devName in devNameList:
            dev = self.devNameDict[devName]
            if dev.conn.isDone() and not dev.conn.isConnected():
                self.showOneDevConnStatus(dev, cmd=cmd)
            else:
                runInBackground = True
                dev.connReq = (False, cmd)
                dev.conn.disconnect()
        return runInBackground
    
    def cmd_exit(self, cmd=None):
        """disconnect yourself"""
        sock = self.getUserSock(cmd.userID)
        sock.close()
    
    def cmd_help(self, cmd=None):
        """print this help"""
        helpList = []
        debugHelpList = []
        
        # commands handled by this actor
        for cmdVerb, cmdFunc in self.locCmdDict.iteritems():
            helpStr = cmdFunc.__doc__.split("\n")[0]
            if ":" in helpStr:
                joinStr = " "
            else:
                joinStr = ": "
            if cmdVerb.startswith("debug"):
                debugHelpList.append(joinStr.join((cmdVerb, helpStr)))
            else:
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
        helpList += ["", "Debug commands:"]
        debugHelpList.sort()
        helpList += debugHelpList
        
        # direct device access commands (these go at the end)
        helpList += ["", "Direct device access commands:"]
        for devName, dev in self.devNameDict.iteritems():
            helpList.append("%s <text>: send <text> to device %s" % (devName, devName))
        
        for helpStr in helpList:
            self.writeToUsers("i", "Text=%r" % (helpStr,), cmd=cmd)
    
    def cmd_ping(self, cmd):
        """verify that actor is alive"""
        cmd.setState("done", textMsg="alive")
    
    def cmd_status(self, cmd):
        """show status

        Actors may wish to override this method to output additional status.
        """
        self.showUserInfo(cmd=cmd)
        self.showDevConnStatus(cmd=cmd)
    
    def cmd_debugMsgs(self, cmd):
        """on/off: turn debugging messages on or off"""
        arg = cmd.cmdArgs.lower()
        if arg == "on":
            self.doDebugMsgs = True
        elif arg == "off":
            self.doDebugMsgs = False
        else:
            raise RuntimeError("Unrecognized argument %r; must be 'on' or 'off'" % (cmd.cmdArgs,))
        self.writeToUsers("i", 'Text="Debugging messages %s"' % (arg,), cmd=cmd)

    def cmd_debugRefCounts(self, cmd):
        """print the reference count for each object"""
        d = {}
        # collect all classes
        for m in sys.modules.values():
            for sym in dir(m):
                o = getattr (m, sym)
                if type(o) in (types.ClassType, types.TypeType):
                    d[o] = sys.getrefcount (o)
        # sort by descending refcount (most interesting objects first)
        pairs = d.items()
        pairs.sort(key=operator.itemgetter(1), reverse=True)

        for c, n in pairs[:100]:
            self.writeToOneUser("i", "RefCount=%5d, %s" % (n, c.__name__), cmd=cmd)
    
    def cmd_debugWing(self, cmd=None):
        """load wingdbstub so you can debug this code using WingIDE"""
        import wingdbstub
        self.writeToUsers("i", 'Text="Debugging with WingIDE enabled"', cmd=cmd)


if __name__ == "__main__":
    import Tkinter
    root = Tkinter.Tk()
    b = Actor(
        userPort = 2005,
    )
    print b.locCmdDict
