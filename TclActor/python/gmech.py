#!/usr/local/bin/python
"""gmech actor

TO DO:
- Move command completion notification is *broken*; why?
- Make INIT more robust by retrying if the first one fails.
  This would clear out the typeahead buffer, for instance.
  I suspect that instead of tying device command INIT to user command init
  it makes more sense to have a special "init" method for the device.
- Measure actual speed and acceleration and set ActuatorKArgs accordingly.
  This would probably be most accurately determined by printing elapsed time for various moves
  (but keep in mind the polling granularity).
- Parse REMAP replies (or if none expected then eliminate them).
- Reduce polling frequency if not moving? If so then be sure to kick it up
  immediately after any move command.
- Test command queueing and collision handling as thoroughly as possible;
  it is complicated and it would be best to test all branches of the code
"""
import math
import re
import time
import Tkinter
import TclActor

ActorPort = 2006
ControllerAddr = "tccserv35m.apo.nmsu.edu"
ControllerPort = 2600
StatusIntervalMS = 500

# keyword arguments for ActuatorModel.__init__
ActuatorKArgs = (
    dict(name="piston", posType=float, posFmt="%0.2f", speed=1.0, accel=1.0),
    dict(name="filter", posType=int,   posFmt="%0d",   speed=0.1, accel=1.0),
)

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
    def __init__(self, name, posType, posFmt, speed, accel=None):
        self.name = name.title()
        self.posType = posType
        if posFmt == None:
            posFmt = {
                float: "%0.1f",
                int: "%d",
            }.get(posType, "%s")
        else:
            self.posFmt = posFmt
        self.speed = abs(float(speed))
        self.accel = abs(float(accel)) if accel != None else None
        
        # items read from status
        self.statusTimestamp = None
        self.pos = None
        self.status = None
        
        # items from a move command
        self.startTime = None
        self.desPos = None
        self.startPos = None
        self.predSec = None # predicted duration of move (in seconds)
    
    def isOK(self):
        """Return True if no bad status bits set (or if status never read)"""
        return (self.status == None) or ((self.status & self.ActuatorBadMask) == 0)
    
    def isMoving(self):
        """Return True if actuator is moving"""
        return (self.status != None) and ((self.status & self.ActuatorHaltedMask) == 0)

    def setStatus(self, pos, status):
        """Set status values. Return True if position or status changed, False otherwise"""
        print "ActuatorModel.setStatus(pos=%s, status=%s)" % (pos, status)
        pos = self.posType(pos)
        status = int(status)
        statusChanged = (pos != self.pos) or (status != self.status)
        self.statusTimestamp = time.time()
        self.pos = pos
        self.status = status
        return statusChanged
    
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
        """Return status string formatted in hub key=value format"""
        strItems = [
            "%s=%s" % (self.name, self._fmt(self.pos)),
        ]
        if self.status == None:
            strItems.append("%sStatus=NaN" % (self.name,))
        else:
            strItems.append("%sStatus=0x%x" % (self.name, self.status))
        if not self.isOK():
            strItems.append("Bad%sStatus" % (self.name,))

        return "; ".join(strItems)

        strItems = [
            ActuatorModel.hubFormat(self),
            "Des%s=%s" % (self.name, self._fmt(self.desPos)),
        ]
        if self.statusTimestamp != None:
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
        return "; ".join(strItems)
    
    def _fmt(self, pos):
        """Return position formatted as a string"""
        if pos == None:
            return "NaN"
        return self.posFmt % (pos,)
    
    def __eq__(self, rhs):
        """Return True if status or move position has changed (aside from status timestamp)"""
        return (self.pos == rhs.pos) \
            and (self.status == rhs.status) \
            and (self.startTime == rhs.startTime)

    def setMove(self, desPos):
        """Call when starting a move to set move-related values.
        
        Inputs:
        - desPos    desired new position
        """
        self.desPos = self.posType(desPos)
        self.startPos = self.pos
        self.startTime = time.time()
        if self.startPos != None:
            # predict duration of move
            dist = abs(float(self.desPos - self.startPos))
            if self.accel == None:
                self.predSec = dist / self.speed
            else:
                # ramp time/distance is time/distance to ramp up to full speed and back down
                rampDist = self.speed / self.accel
                if dist <= rampDist:
                    self.predSec = 2.0 * math.sqrt(dist / self.accel)
                else:
                    rampTime = 2.0 * self.speed / self.accel
                    self.predSec = rampTime + ((dist - rampDist) / self.speed)


class GMechDev(TclActor.TCPDevice):
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
    def __init__(self, callFunc=None, actor=None):
        TclActor.TCPDevice.__init__(self,
            name = "gmech",
            addr = ControllerAddr,
            port = ControllerPort,
            sendLocID = False,
            callFunc = callFunc,
            actor = actor,
        )
        self.statusID = None # "after" ID of next status command
        # dictionary of actuator (piston or filter): actuator status
        self.actuatorStatusDict = {}
        for actArgs in ActuatorKArgs:
            self.actuatorStatusDict[actArgs["name"]] = ActuatorModel(**actArgs)
        self.currCmd = None
        self.cmdQueue = []
        self.reqNReplies = 0 # number of replies wanted by this comand, including echo
        self.nReplies = 0 # number of replies read for current command, including echo
        self.currCmdTimer = None # ID of command timeout timer
        self.pendingCmd = None # only used to cancel REMAP -- OBSOLETE; use cmdQueue instead
        self._tk = Tkinter.Frame()
        self.conn.addStateCallback(self.devConnStateCallback)
    
    def getActuatorModelStr(self, actuatorStatus):
        # note: order of severity is 0, 1, 2... so just plow through the bits in order
        for bit in range(self.MaxActuatorBit):
            bitSet = (actuatorStatus >> bit) & 0x1
            if bitSet:
                return ActatorBitDict[bitSet]
        return ""
    
    def devConnStateCallback(self, devConn):
        """Called when a device's connection state changes."""
        print "devConnStateCallback; state=%s" % (devConn.getFullState(),)
        if devConn.isConnected():
            self.queryStatus()
        else:
            self.cancelQueryStatus()
    
    def cancelQueryStatus(self):
        """Cancel background status query, if any"""
        if self.statusID:
            self._tk.after_cancel(self.statusID)
            self.statusID = None
    
    def queryStatus(self):
        """Query status at regular intervals"""
        print "queryStatus"
        self.cancelQueryStatus()
        if not (self.currCmd or self.cmdQueue):
            # not busy; go ahead and request status
            statusCmd = TclActor.DevCmd("STATUS")
            self.startCmd(statusCmd)
        self.statusID = self._tk.after(StatusIntervalMS, self.queryStatus)
    
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
        print "GMechDev.handleReply: replyStr=%r; nReplies=%s" % (replyStr, self.nReplies)
        replyList = replyStr.rsplit(None, 1)
        isDone = replyList[-1] == "OK"
        if len(replyList) == 1 and isDone:
            replyData = ""
        else:
            replyData = replyList[0]
            
        # handle reply data
        if replyData:
            self.nReplies += 1
            if self.nReplies == 1:
                # first reply is command echo
                if replyData != self.currCmd.cmdStr.strip():
                    self.currCmd.setState("failed", "Bad command echo: read %r; wanted %r" % \
                        (replyData, self.currCmd.cmdStr.strip()))
                    return
            elif self.currCmd.cmdVerb == "STATUS" and self.nReplies == 2:
                # parse status
                statusMatch = self._CtrllrStatusRE.match(replyData)
                if not statusMatch:
                    self.currCmd.setState("failed", "Could not parse status reply %r" % (replyData,))
                    return
                matchDict = statusMatch.groupdict()
                for act, actStatus in self.actuatorStatusDict.iteritems():
                    statusChanged = actStatus.setStatus(
                        pos = matchDict[act],
                        status = matchDict["%sStatus" % (act,)],
                    )

                    # print status if status was user-requested or has changed
                    if (self.currCmd.userID != 0) or statusChanged:
                        self.actor.writeToUsers("i", actStatus.hubFormat(), cmd=self.currCmd)
                        
            elif self.currCmd.cmdVerb == "REMAP":
                # probably should parse this data, but for now just spit it out...
                self.actor.writeToUsers("i", "RemapData=%s" % (quoteStr(replyData)), cmd=self.currCmd)
            else:
                # only REMAP or STATUS should get any replies
                self.currCmd.setState("failed", "Unexpected reply %r" % (replyStr,))
        
        if isDone and self.currCmd:
            if self.nReplies < 1:
                self.currCmd.setState("failed", "No command echo")
            else:
                self.currCmd.setState("done")

        if isDone or (replyData and self.nReplies > 1):
            self._doCallbacks()
    
    def setCurrCmd(self, cmd=None, timeLimitMS=None):
        """Set or clear current command.
        
        Inputs:
        - cmd       new command or None if clearing an existing command
        - timeLimitMS   time limit for command (in ms); None if no limit
        """
        self.currCmd = cmd
        self.nReplies = 0
        if self.currCmdTimer:
            self._tk.after_cancel(self.currCmdTimer)
        if timeLimitMS:
            self.currCmdTimer = self._tk.after(timeLimitMS, self.cmdTimeout, cmd)
        else:
            self.currCmdTimer = None
    
    def cmdCallback(self, cmd):
        """Handle command state callback"""
        if not cmd.isDone():
            return
        if cmd == self.currCmd:
            self.setCurrCmd(None)
        else:
            sys.stderr.write("Bug: GMechActor.cmdCallback got command callback but command was not current command!\n")
        if self.cmdQueue:
            nextCmd = self.cmdQueue.pop(0)
            self.startCmd(nextCmd)
    
    def cmdTimeout(self, cmd):
        if self.currCmd != cmd:
            sys.stderr.write("Warning: command time expired but command has changed\n")
            return
        self.currCmd.setState("failed", "Timed out")

    def startCmd(self, cmd):
        """Start a gmech controller command"""
        print "GMechDev.startCmd(%s)" % (cmd,)
        if not self.conn.isConnected():
            raise RuntimeError("Device %s is not connected" % (self.name,))

        cmd.locCmdID = 0
        if self.currCmd:
            # queue up the command unless the existing command is remap
            if cmd.cmdVerb == "INIT":
                # clear the command queue and replace with this init command
                for queuedCmd in self.cmdQueue:
                    queuedCmd.setState("cancelled", "Superseded by INIT")
                self.cmdQueue = [cmd]
                
                # if REMAP is running cancel it (other commands run quickly and can't be cancelled)
                if self.currCmd.cmdVerb == "REMAP":
                    self.conn.writeLine("") # start cancelling REMAP
                    self.currCmd.cmdVerb.setState("cancelled", "Superseded by INIT")
                return

            # command cannot be queued behind remap because it's so slow
            # (remap *can* be cancelled by INIT but that is handled above)
            if self.currCmd.cmdVerb == "REMAP":
                cmd.setState("failed", "Busy executing remap")
                return

            queuedCmdSet = set(pcmd.cmdVerb for pcmd in self.cmdQueue)
            if "REMAP" in queuedCmdSet:
                cmd.setState("failed", "Remap is queued")
                return
            if cmd.cmdVerb in queuedCmdSet:
                # supersede existing version of this command
                newCmdQueue = []
                for queuedCmd in self.cmdQueue:
                    if queuedCmd.cmdVerb == cmd.cmdVerb:
                       queuedCmd.setState("cancelled", "Superseded") 
                    else:
                        newCmdQueue.append(queuedCmd)
                self.cmdQueue = newCmdQueue
            self.cmdQueue.append(cmd)
        else:
            if cmd.cmdVerb == "REMAP":
                timeLimitMS = None
            else:
                timeLimitMS = 2000
            self.setCurrCmd(cmd, timeLimitMS)
            cmd.addCallback(self.cmdCallback)
            # self._tk.call('puts', self.conn._sock, cmd.cmdStr)
            print "GMechDev.startCmd writing %r" % (cmd.cmdStr,)
            self.conn.writeLine(cmd.cmdStr)


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
            devs = GMechDev(callFunc=self.updateCtrllrState, actor=self),
        )
        self.ctrllr = self.devNameDict["gmech"]
        self.moveCmdDict = {} # dict of cmdVerb: userCmd for actuator moves
    
    def cancelSameCmd(self, newCmd):
        """Cancel a command of the same verb, if present"""
        cmdToCancel = self.moveCmdDict.pop(newCmd.cmdVerb, None)
        if cmdToCancel:
            cmdToCancel.setState("cancelled", "superseded by %r" % (newCmd.cmdStr,))
    
    def checkLocalCmd(self, newCmd):
        """Check if a new local command can run given what else is going on.
        If not then raise TclActor.ConflictError(reason).
        If it can run but an existing command must be superseded then supersede the old command here.

        Note that each cmd_foo method can perform additional checks and cancellation.
        """
        if not self.moveCmdDict:
            return
        if "init" in self.moveCmdDict:
            raise TclActor.ConflictError("Busy running init")
        if "status" in self.moveCmdDict:
            raise TclActor.ConflictError("Busy running status")
            return
        if "remap" in self.moveCmdDict and newCmd.cmdVerb != "init":
            raise TclActor.ConflictError("Busy running remap (use init to cancel)")
    
    def cmdCallback(self, cmd):
        """Let Actor handle normal command completion, then remove command from moveCmdDict (if present)"""
        print "cmdCallback:", cmd.cmdID, cmd.cmdVerb
        TclActor.Actor.cmdCallback(self, cmd)
        if cmd.isDone():
            foo = self.moveCmdDict.pop(cmd.cmdVerb, None)
            if foo:
                print "popped command"
            else:
                print "could not find command to pop"

    def newUserOutput(self, userID, tkSock):
        """Report status to new users"""
        for actuator, fullStatus in self.ctrllr.actuatorStatusDict.iteritems():
            msgCode = ":" if fullStatus.isOK() else "w"
            statusStr = fullStatus.hubFormat()
            self.writeToOneUser(msgCode, statusStr, userID=userID)
    
    def startDevCmd(self, devCmdStr, userCmd=None):
        """Send a command string to the gmech controller.
        If userCmd is specified then it will track the device command
        (i.e. when the device command finishes or fails then so does the user command).
        """
        print "startDevCmd(%s)" % (devCmdStr)
        devCmd = TclActor.DevCmd(cmdStr=devCmdStr, userCmd=userCmd)
        self.ctrllr.startCmd(devCmd)
    
    def updateCtrllrState(self, dev):
        """Called whenever the state of the gmech device changes"""
        print "updateCtrllrState"
        # if a move finished then report success or failure
        for actuator, fullStatus in self.ctrllr.actuatorStatusDict.iteritems():
            if fullStatus.isMoving():
                print "Actuator %s is moving" % (actuator,)
                continue
            moveCmd = self.moveCmdDict.get("piston")
            print "Actuator %s is halted; moveCmd=%s" % (actuator, moveCmd)
            if moveCmd:
                if fullStatus.isOK():
                    moveCmd.setState("done")
                else:
                    stateStr = dev.getActuatorModelStr(dev.pistonStatus)
                    moveCmd.setState("failed", stateStr)

    def cmd_status(self, cmd=None):
        """display status"""
        self.checkNoArgs(cmd)
        self.startDevCmd("STATUS", userCmd=cmd)
    
    def cmd_filter(self, cmd):
        """filterNum: set the NA2 guider filter number"""
        filter = int(cmd.cmdArgs)
        devCmdStr = "FILTER %d" % (filter,)
        self.cancelSameCmd(cmd)
        self.moveCmdDict[cmd.cmdVerb] = cmd
        self.startDevCmd(devCmdStr)
    
    def cmd_init(self, cmd=None):
        """initialize the NA2 guider mechanical controller and this actor"""
        self.checkNoArgs(cmd)
        for cmdVerb in self.ctrllr.actuatorStatusDict:
            cmdToCancel = self.moveCmdDict.get(cmdVerb)
            if cmdToCancel:
                cmdToCancel.setState("cancelled", "superseded by init")
        self.startDevCmd("INIT", userCmd=cmd)

    def cmd_piston(self, cmd):
        """piston: set the NA2 guider piston in um"""
        piston = float(cmd.cmdArgs)
        devCmdStr = "PISTON %0.1f" (piston,)
        self.cancelSameCmd(cmd)
        self.moveCmdDict[cmd.cmdVerb] = cmd
        self.startDevCmd(devCmdStr)
    
    def cmd_remap(self, cmd=None):
        """remap actuators and reset controller"""
        self.checkNoArgs(cmd)
        self.startDevCmd("REMAP", userCmd=cmd)


if __name__ == "__main__":
    import Tkinter
    root = Tkinter.Tk()
    b = GMechActor()
    root.mainloop()
