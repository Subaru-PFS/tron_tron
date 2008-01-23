#!/usr/local/bin/python
"""gmech actor

TO DO:
- Refine piston motion timings based on recent measurements.
- Document UnknownCommand, MemRefs
  Remove "users" command -- use status instead.
  Document actor-common keywords in TclActor manual? It'd be nice to do an inclusion if possible.
- Should status be output when device disconnected?
- Test command queueing and collision handling as thoroughly as possible;
  it is complicated and it would be best to test all branches of the code.
- Consider making INIT more robust. Some possibilities:
    - Retry if the first one fails
    - Send some more complicated sequence such as <CR>INIT and handle command echo carefully
    (e.g. ignore all replies until OK, then check last replyData == "INIT")
"""
import math
import re
import sys
import time
import Tkinter
from RO.StringUtil import quoteStr
import TclActor

ActorPort = 2006
ControllerAddr = "tccserv35m.apo.nmsu.edu"
ControllerPort = 2600
StatusIntervalMovingMS = 500
StatusIntervalHaltedMS = 20000

class ActuatorModel(object):
    """Basic status for an actuator
    
    Inputs
    - name      name of actuator; used for formatted output (case adjusted accordingly)
    - posType   type of position (typically int or float)
    - posFmt    format string for position (e.g. "%0.1f");
                if None then a default is chosen based on posType
    - speed     maximum speed in units-of-position/second
    - accel     fixed acceleration in units-of-position/second^2;
                if omitted or None then acceleration is infinite
    
    Speed and acceleration are used to predict motion time.
    """
    ActuatorHaltedMask = 0x20   # actuator powered down
    ActuatorGoodMask = 0x10     # at commanded position
    ActuatorBadMask = 0x0F      # limit switch 1 or 2 engaged or at max or min position
    # actuator info is a dict of name: (posType, posFmt, minPos, maxPos, tconst, speed, accel)
    # tconst, speed and accel are used to predict motion time
    ActuatorInfo = dict(
        piston = (float, "%0.2f", -3.0, 152403.0, 0.42, 1587.4, None),
        filter = (int,   "%0d",    0,        6,   0.42, 2.0, 2.4),
    )
    def __init__(self, name, actor):
        actInfo = self.ActuatorInfo.get(name)
        if not actInfo:
            raise RuntimeError("Unknown actuator %r" % (name,))
        self.name = name.title()
        self.actor = actor
        self.posType, self.posFmt, self.minPos, self.maxPos, self.tconst, self.speed, self.accel = actInfo
        
        self.moveCmd = None
        self.clear()
    
    def cancelMove(self, msg="Superseded"):
        """Mark the current motion command (if any) as cancelled.
        Warning: this does not communicate with the controller!
        """
        if self.moveCmd:
            if self.moveCmd.isDone():
                textMsg = "Bug: move command %s is done and is being purged" % (self.moveCmd,)
                self.actor.writeToUsers("w", "Text=%s" % (quoteStr(textMsg),))
            else:
                self.moveCmd.setState("cancelled", hubMsg="Superseded")
        self._clearMove()
    
    def clear(self):
        """Clear all information; call if the connection is lost or for INIT or REMAP"""
        if self.moveCmd:
            self.moveCmd.setState("failed", hubMsg="LostConnection")
        self._clearMove()
        self._clearStatus()
    
    def copy(self, statusToCopy):
        """Copy items from another ActuatorModel object"""
        if self.name != statusToCopy.name:
            raise RuntimeError("Names do not match")
        if self.posType != statusToCopy.posType:
            raise RuntimeError("Position types do not match")
        
        # items read from status
        self.statusTimestamp = statusToCopy.statusTimestamp
        self.pos = statusToCopy.pos
        self.status = statusToCopy.status
        
        # items from a move command
        self.startTime = statusToCopy.startTime
        self.desPos = statusToCopy.desPos
        self.startPos = statusToCopy.startPos
        self.predSec = statusToCopy.predSec

    def hubFormat(self):
        """Return (msgCode, msgStr) for output of status as a hub-formatted message"""
        msgCode = "i" if self.isOK() else "w"
        strItems = [
            "%s=%s" % (self.name, self._fmt(self.pos)),
        ]
        if self.status == None:
            strItems.append("%sStatus=NaN" % (self.name,))
        else:
            strItems.append("%sStatus=0x%x" % (self.name, self.status))
        if not self.isOK():
            strItems.append("Bad%sStatus" % (self.name,))

        strItems.append("Des%s=%s" % (self.name, self._fmt(self.desPos)))
        if self.startTime != None:
            if self.isMoving():
                elapsedSec = time.time() - self.startTime
                strItems += [
                    "%sPredTotalSec=%0.1f" % (self.name, self.predSec),
                    "%sElapsedSec=%0.1f" % (self.name, elapsedSec),
                ]
            else:
                if self.desPos != None:
                    posErr = self.pos - self.desPos
                else:
                    posErr = None
                strItems.append("%sError=%s" % (self.name, self._fmt(posErr)))
        return (msgCode, "; ".join(strItems))
    
    def isOK(self):
        """Return True if no bad status bits set (or if status never read)"""
        return (self.status == None) or ((self.status & self.ActuatorBadMask) == 0)
    
    def isMoving(self):
        """Return True if actuator is moving"""
        return (self.status != None) and ((self.status & self.ActuatorHaltedMask) == 0)
    
    def setMove(self, moveCmd):
        """Call just before sending a move command to the controller.
        
        Vet the arguments and coerce to proper type.
        
        Raise RuntimeError after marking move as failed if command is invalid
        
        Inputs:
        - desPos    desired new position
        """
        # check type of position string and force the format (the gmech controller is picky)
        try:
            desPos = self.posType(moveCmd.cmdArgs)
            moveCmd.cmdArgs = self.posFmt % (desPos,)
            moveCmd.cmdStr = ("%s %s" % (moveCmd.cmdVerb, moveCmd.cmdArgs))
        except Exception, e:
            moveCmd.setState("failed", textMsg="Could not parse position %r" % (moveCmd.cmdArgs),
                hubMsg="Exception=%s" % (quoteStr(str(e)),))
            raise RuntimeError(e)

        # check limits
        if (self.minPos != None) and (desPos < self.minPos):
            errMsg = "Position too small: %s < %s" % (desPos, self.minPos)
            moveCmd.setState("failed", textMsg=errMsg)
            raise RuntimeError(errMsg)
        if (self.maxPos != None) and (desPos > self.maxPos):
            errMsg = "Position too large: %s > %s" % (desPos, self.maxPos)
            moveCmd.setState("failed", textMsg=errMsg)
            raise RuntimeError(errMsg)
            
        moveCmd.addCallback(self._moveCmdCallback)

        self.cancelMove()
        self.moveCmd = moveCmd
        self.desPos = desPos
        self.startPos = self.pos
        self.startTime = time.time()
        if self.startPos != None:
            # predict duration of move
            dist = abs(float(self.desPos - self.startPos))
            if self.accel == None:
                self.predSec = dist / self.speed
            else:
                # ramp time/distance is time/distance to ramp up to full speed and back down
                rampDist = self.speed**2 / self.accel
                if dist <= rampDist:
                    self.predSec = 2.0 * math.sqrt(dist / self.accel)
                else:
                    rampTime = 2.0 * self.speed / self.accel
                    self.predSec = rampTime + ((dist - rampDist) / self.speed)
            self.predSec += self.tconst

    def setStatus(self, pos, status, cmd=None):
        """Set status values."""
        pos = self.posType(pos)
        status = int(status)
        statusChanged = (pos != self.pos) or (status != self.status) or (self.statusTimestamp == None)
        self.statusTimestamp = time.time()
        self.pos = pos
        self.status = status
        if statusChanged or (cmd and cmd.userID != 0):
            msgCode, statusStr = self.hubFormat()
            self.actor.writeToUsers(msgCode, statusStr, cmd=cmd)
        
        if self.moveCmd and not self.isMoving():
            if self.isOK():
                #print "%s moved %s in %s seconds" % (self.name, abs(self.pos - self.startPos), time.time() - self.startTime)
                self.moveCmd.setState("done")
            else:
                self.moveCmd.setState("failed", textMsg="Bad actuator status")
    
    def _clearMove(self):
        """Clear all move command information.
        Be careful not to call unless the move command has finished.
        """
        if self.moveCmd and not self.moveCmd.isDone():
            self.moveCmd.setState("failed", textMsg="Bug: move command cancelled by GMechDev._clearMove")
        self.moveCmd = None
        self.startTime = None
        self.desPos = None
        self.predSec = None # predicted duration of move (in seconds)
    
    def _clearStatus(self):
        """Clear status data"""
        self.statusTimestamp = None
        self.pos = None
        self.status = None
    
    def _fmt(self, pos):
        """Return position formatted as a string"""
        if pos == None:
            return "NaN"
        return self.posFmt % (pos,)
    
    def _moveCmdCallback(self, cmd):
        """Callback function for move commands"""
        if cmd.isDone():
            self._clearMove()
    
    def __eq__(self, rhs):
        """Return True if status or move position has changed (aside from status timestamp)"""
        return (self.pos == rhs.pos) \
            and (self.status == rhs.status) \
            and (self.startTime == rhs.startTime)


class GMechDev(TclActor.TCPDevice):
    """Object representing the gmech hardware controller.
    
    Note: commands are converted to uppercase in the newCmd method.
    """
    MaxPistonError = 1.0
    ActuatorBitDict = {
        0: "At forward limit switch",
        1: "At reverse limit switch",
        2: "At maximum position",
        3: "At minimum position",
        4: "At requested position",
        5: "Actuator powered down",
    }
    MaxActuatorBit = max(ActuatorBitDict.keys())
    _CtrllrStatusRE = re.compile(r"(?P<piston>\d+\.\d+)\s+(?P<filter>\d+)\s+(?:\d+\.\d+)\s+(?P<pistonStatus>\d+)\s+(?P<filterStatus>\d+)")
    _CharsToStrip = "".join([chr(n) for n in xrange(33)]) # control characters and whitespace
    _DefTimeLimitMS = 2000
    def __init__(self, callFunc=None, actor=None):
        TclActor.TCPDevice.__init__(self,
            name = "gmech",
            addr = ControllerAddr,
            port = ControllerPort,
            callFunc = callFunc,
            actor = actor,
            cmdInfo = (
              ("init",   None, "initialize the gmech controller"),
              ("remap",  None, "remap the piston and filter actuators and reset the gmech controller"),
              ("piston", None, "um: set the guider piston (focus)"),
              ("filter", None, "filtnum: select guider filter number (0-6)"),
            ),
        )
        self.queryStatusTimer = None # "after" ID of next queryStatus command
        # dictionary of actuator (piston or filter): actuator status
        self.actuatorStatusDict = {}
        for actName in ActuatorModel.ActuatorInfo.keys():
            self.actuatorStatusDict[actName] = ActuatorModel(actName, self.actor)
        self.cmdQueue = []
        self.currCmd = None
        self.nReplies = 0 # number of replies read for current command, including echo
        self.currCmdTimer = None # ID of command timeout timer
        self.pendingCmd = None # only used to cancel REMAP -- OBSOLETE; use cmdQueue instead
        self._tk = Tkinter.Frame()
        self.conn.addStateCallback(self.connStateCallback)
    
    def getActuatorModelStr(self, actuatorStatus):
        # note: order of severity is 0, 1, 2... so just plow through the bits in order
        for bit in range(self.MaxActuatorBit):
            bitSet = (actuatorStatus >> bit) & 0x1
            if bitSet:
                return ActatorBitDict[bitSet]
        return ""
    
    def connStateCallback(self, devConn):
        """Called when a device's connection state changes."""
        if devConn.isConnected():
            self.queryStatus()
        else:
            self.cancelQueryStatus()
            for actStatus in self.actuatorStatusDict.itervalues():
                actStatus.clear()
    
    def cancelQueryStatus(self):
        """Cancel background status query, if any"""
        if self.queryStatusTimer:
            self._tk.after_cancel(self.queryStatusTimer)
            self.queryStatusTimer = None
    
    def queryStatus(self):
        """Query status at regular intervals.
        """
        self.cancelQueryStatus()
        needNewStatus = True
        if self.currCmd and self.currCmd.cmdVerb == "STATUS":
            needNewStatus = False
        else:
            for queuedCmd in self.cmdQueue:
                if queuedCmd.cmdVerb == "STATUS":
                    needNewStatus = False
                    break
        if needNewStatus:
            self.newCmd("STATUS")
        
        isMoving = False
        for actStatus in self.actuatorStatusDict.itervalues():
            isMoving = isMoving or actStatus.moveCmd
        intervalMS = StatusIntervalMovingMS if isMoving else StatusIntervalHaltedMS
        self.queryStatusTimer = self._tk.after(intervalMS, self.queryStatus)
    
    def handleReply(self, replyStr):
        """Handle a line of output from the device.
        Called whenever the device outputs a new line of data.
        
        Inputs:
        - replyStr  the reply, minus any terminating \n
        
        Tasks include:
        - Parse the reply
        - Manage the pending commands
        - Output data to users
        - Parse status to update the model parameters
        - If a command has finished, call the appropriate command callback
        """
        if not self.currCmd:
            # ignore unsolicited input
            return
        replyStr = replyStr.encode("ASCII", "ignore").strip(self._CharsToStrip)
        if not replyStr:
            # ignore blank replies
            return
        replyList = replyStr.rsplit(None, 1)
        isDone = replyList[-1] == "OK"
        if len(replyList) == 1 and isDone:
            replyData = ""
        else:
            replyData = replyList[0]
        if self.actor.doDebugMsgs:
            debugMsg = "GMechDev.handleReply: replyStr=%r; nReplies=%s; currCmd=%s" % (replyStr, self.nReplies, self.currCmd)
            self.actor.writeToUsers("i", "DebugText=%s" % quoteStr(debugMsg))
            
        # handle reply data
        if replyData:
            self.nReplies += 1
            if self.nReplies == 1:
                # first reply is command echo
                if replyData != self.currCmd.cmdStr.strip():
                    self.currCmd.setState("failed", textMsg="Bad command echo: read %r; wanted %r" % \
                        (replyData, self.currCmd.cmdStr.strip()))
                    return
            elif self.currCmd.cmdVerb == "STATUS" and self.nReplies == 2:
                # parse status
                statusMatch = self._CtrllrStatusRE.match(replyData)
                if not statusMatch:
                    self.currCmd.setState("failed", textMsg="Could not parse status reply %r" % (replyData,))
                    return
                matchDict = statusMatch.groupdict()
                for act, actStatus in self.actuatorStatusDict.iteritems():
                    actStatus.setStatus(
                        pos = matchDict[act],
                        status = matchDict["%sStatus" % (act,)],
                        cmd = self.currCmd,
                    )
                        
            elif self.currCmd.cmdVerb == "REMAP" and replyData.endswith("abborted"):
                # remap abort seen
                if not self.currCmd.isFailing():
                    self.currCmd.setState("failing", textMsg = "Remap is unexpectedly aborting")
            else:
                # only REMAP or STATUS should get any replies
                self.currCmd.setState("failing", textMsg="Unexpected reply %r" % (replyStr,))
        
        if isDone and self.currCmd:
            if self.currCmd.isFailing():
                self.currCmd.setState("failed")
            elif self.nReplies < 1:
                self.currCmd.setState("failed", textMsg="No command echo")
            elif (self.currCmd.cmdVerb == "STATUS") and (self.nReplies < 2):
                self.currCmd.setState("failed", textMsg="Status not seen")
            else:
                # successful completion
                # if actuator command then mark as started
                actStatus = self.actuatorStatusDict.get(self.currCmd.cmdVerb.lower())
                if actStatus:
                    # an actuator move; print "started" and remove from self.currCmd
                    # and start next command (if any)
                    self.actor.writeToUsers("i", "Started", cmd=self.currCmd)
                    self.clearCurrCmd()
                else:
                    # command does not run in the background; it's really done now
                    self.currCmd.setState("done")

        if isDone or (replyData and self.nReplies > 1):
            self._doCallbacks()
        
    def clearCurrCmd(self):
        """Clear current command (if any) and start next queued command (if any)
        Warning: does NOT change the state of the current command.
        """
        self.currCmd = None
        self.nReplies = 0
        if self.currCmdTimer:
            self._tk.after_cancel(self.currCmdTimer)
        self.currCmdTimer = None
        if self.cmdQueue:
            nextCmd = self.cmdQueue.pop(0)
            self.startCmd(nextCmd)
    
    def startCmd(self, cmd, timeLimitMS=_DefTimeLimitMS):
        """Send a command to the device; there must be no current command"""
        if self.currCmd or self.currCmdTimer:
            raise RuntimeError("Current command and/or command timer exists")
        if self.actor.doDebugMsgs:
            debugMsg = "GMechDev.startCmd cmd=%s; timeLimitMS=%s" % (cmd, timeLimitMS)
            self.actor.writeToUsers("i", "DebugText=%s" % quoteStr(debugMsg))

        # if this is an actuator move then vet the arguments and set actuator status
        isMove = False
        actStatus = self.actuatorStatusDict.get(cmd.cmdVerb.lower())
        if actStatus:
            # this is an actuator move
            isMove = True
            try:
                actStatus.setMove(cmd)
            except RuntimeError, e:
                self.clearCurrCmd() # try next command, if any
                return
        
        if cmd.isDone(): # sanity check
            raise RuntimeError("Bug: %s already finished" % (cmd,))

        self.currCmd = cmd
        if timeLimitMS:
            self.currCmdTimer = self._tk.after(timeLimitMS, self.cmdTimeout, cmd)
        if not isMove:
            cmd.addCallback(self.cmdCallback)
        self.conn.writeLine(cmd.cmdStr)

        if isMove:
            self.queryStatus()
        elif cmd.cmdVerb in ("INIT", "REMAP"):
            for actStatus in self.actuatorStatusDict.itervalues():
                actStatus.clear()
            self.queryStatus()
            if cmd.cmdVerb == "REMAP":
                self.actor.writeToUsers("i", "Started", cmd=cmd)
    
    def cmdCallback(self, cmd):
        """Handle command state callback"""
        if not cmd.isDone():
            return
        if cmd == self.currCmd:
            self.clearCurrCmd()
        else:
            sys.stderr.write("Bug: GMechActor.cmdCallback got command callback but command was not current command!\n")
    
    def cmdTimeout(self, cmd):
        if self.currCmd != cmd:
            sys.stderr.write("Warning: command time expired but command has changed\n")
            return
        self.currCmd.setState("failed", hubMsg="Timeout")

    def newCmd(self, cmdStr, callFunc=None, userCmd=None):
        """Start a new command"""
        if self.actor.doDebugMsgs:
            debugMsg = "GMechDev.newCmd cmdStr=%s; callFunc=%s; userCmd=%s" % (cmdStr, callFunc, userCmd)
            self.actor.writeToUsers("i", "DebugText=%s" % quoteStr(debugMsg))
        if not self.conn.isConnected():
            errMsg = "Device %s is not connected" % (self.name,)
            if userCmd:
                userCmd.setState("failed", textMsg=errMsg)
            else:
                self.actor.writeToUsers("w", "Text=%s" % (quoteStr(errMsg),))
            return
        
        # force command string to uppercase for gmech device
        cmd = self.cmdClass(cmdStr.upper(), callFunc=callFunc, userCmd=userCmd)
        
        # if command is INIT then purge queued commands and cancel the current command if possible
        if cmd.cmdVerb == "INIT":
            # clear the command queue
            for actStatus in self.actuatorStatusDict.itervalues():
                actStatus.cancelMove("Superseded by init")
            for queuedCmd in self.cmdQueue:
                if queuedCmd.isDone():
                    textMsg = "Bug: queued command %s is done and is being purged" % (cmd,)
                    self.actor.writeToUsers("w", "Text=%s" % (quoteStr(textMsg),))
                else:
                    queuedCmd.setState("cancelled", textMsg="Superseded by init", hubMsg="Superseded")
            self.cmdQueue = []

            if self.currCmd:
                if self.currCmd.isDone():
                    textMsg = "Bug: current command %s is done and is being purged" % (self.currCmd,)
                    self.actor.writeToUsers("w", "Text=%s" % (quoteStr(textMsg),))
                    self.currCmd = None
                elif self.currCmd.cmdVerb == "REMAP":
                    # remap can be cancelled; other commands cannot
                    self.currCmd.setState("cancelling", textMsg="Superseded by init")
                    # reset timeout timer
                    if self.currCmdTimer:
                        self._tk.after_cancel(self.currCmdTimer)
                    else:
                        self.actor.writeToUsers("w", "Text=Bug: cancelling REMAP but no command timer")
                    self.currCmdTimer = self._tk.after(self._DefTimeLimitMS, self.cmdTimeout, self.currCmd)
                    self.conn.writeLine("") # start cancelling REMAP

        if self.currCmd:
            # command cannot be queued behind remap because it's so slow
            # (remap *can* be cancelled by INIT but that is handled above)
            if self.currCmd.cmdVerb == "REMAP":
                cmd.setState("failed", textMsg="Busy executing remap")
                return

            queuedCmdSet = set(pcmd.cmdVerb for pcmd in self.cmdQueue)
            if "REMAP" in queuedCmdSet:
                cmd.setState("failed", textMsg="Remap is queued")
                return
            if cmd.cmdVerb in queuedCmdSet:
                # supersede existing version of this command
                newCmdQueue = []
                for queuedCmd in self.cmdQueue:
                    if queuedCmd.cmdVerb == cmd.cmdVerb:
                       queuedCmd.setState("cancelled", hubMsg="Superseded") 
                    else:
                        newCmdQueue.append(queuedCmd)
                self.cmdQueue = newCmdQueue
            self.cmdQueue.append(cmd)
        else:
            if cmd.cmdVerb == "REMAP":
                timeLimitMS = None
            else:
                timeLimitMS = 2000
            
            self.startCmd(cmd, timeLimitMS)


class GMechActor(TclActor.Actor):
    """gmech actor: interfaces to the NA2 guider mechanical controller.
    
    Inputs:
    - userPort      port on which to listen for users
    - maxUsers      the maximum allowed # of users (if None then no limit)
    
    Comments:
    - Some user commands are tied to a controller command in that when the controller command
      finishes (or fails) the user command does the same. These are: status, init and remap
      (and the direct device commands).
    - Other user commands do not finish until the status is appropriate
      (though they may get superseded before then). These are: filter, piston.
    """
    def __init__(self):
        TclActor.Actor.__init__(self,
            userPort = ActorPort,
            maxUsers = None,
            devs = GMechDev(actor=self),
        )
        self.gmechDev = self.devNameDict["gmech"]
        self.moveCmdDict = {} # dict of cmdVerb: userCmd for actuator moves
    
    def newUserOutput(self, userID, tkSock):
        """Report status to new user"""
        for actuator, actStatus in self.gmechDev.actuatorStatusDict.iteritems():
            msgCode, statusStr = actStatus.hubFormat()
            self.writeToOneUser(msgCode, statusStr, userID=userID)
    
    def cmd_status(self, cmd=None):
        """Show device status
        """
        TclActor.Actor.cmd_status(self, cmd)
        if self.gmechDev.conn.isConnected():
            self.gmechDev.newCmd("STATUS", userCmd=cmd)
            return True # command executes in background
        else:
            for actObj in self.gmechDev.actuatorStatusDict.values():
                msgCode, statusStr = actObj.hubFormat()
                self.writeToUsers(msgCode, statusStr, cmd=cmd)


if __name__ == "__main__":
    import Tkinter
    root = Tkinter.Tk()
    b = GMechActor()
    root.mainloop()
