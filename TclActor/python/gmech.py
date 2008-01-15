#!/usr/local/bin/python
"""gmech actor

TO DO:
- Fix gmech controller communications
- Measure actual speed and acceleration
- Assume that REMAP gets replies: figure out a good way to print them.
  That same solution will probably make for a cleaner way to print STATUS
  (e.g. it's not obvious to me that special code in the actor is required;
  it might make more sense to be able to send information through a command;
  if so then the background status commands can be high-level commands with userID=cmdID=0)
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

# keyword arguments for ActuatorBasicInfo or ActuatorFullInfo __init__
ActuatorKArgs = (
    dict(name="piston", posType=int,   posFmt="%d",    speed=1.0, accel=1.0),
    dict(name="filter", posType=float, posFmt="%0.2f", speed=0.1, accel=1.0),
)

class ActuatorBasicInfo(object):
    """Basic status for an actuator
    
    Inputs:
    - name      name of actuator; used for formatted output (case adjusted accordingly)
    - posType   type of position (typically int or float)
    - posFmt    format string for position (e.g. "%0.1f");
                if None then a default is chosen based on posType
    additional keyword arguments are ignored
    """
    ActuatorHaltedMask = 0x20   # actuator powered down
    ActuatorGoodMask = 0x10     # at commanded position
    ActuatorBadMask = 0x0F      # limit switch 1 or 2 engaged or at max or min position
    def __init__(self, name, posType, posFmt=None, **dumKArgs):
        self.name = name.title()
        self.posType = posType
        if posFmt == None:
            posFmt = {
                float: "%0.1f",
                int: "%d",
            }.get(posType, "%s")
        else:
            self.posFmt = posFmt
        self.pos = None
        self.status = None
        self.timestamp = None
    
    def isOK(self):
        """Return True if no bad status bits set (or if status never read)"""
        return (self.status == None) or (self.status & self.ActuatorBadMask) == 0
    
    def isMoving(self):
        """Return True if actuator is moving"""
        return (self.status != None) and (self.status & self.ActuatorHaltedMask) != 0

    def set(self, pos, status):
        """Set the values"""
        print "ActuatorBasicInfo.set(pos=%s, status=%s)" % (pos, status)
        pos = self.posType(pos)
        status = int(status)
        self.pos = pos
        self.status = status
        self.timestamp = time.time()
    
    def copy(self, statusToCopy):
        """Copy items from another ActuatorBasicInfo object"""
        if self.posType != statusToCopy.posType:
            raise RuntimeError("Position types do not match")
        self.pos = statusToCopy.pos
        self.status = statusToCopy.status
        self.timestamp = statusToCopy.timestamp

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
        if not self.isMoving():
            strItems.append("Final%s=%s" % (self.name, self._fmt(self.pos)))

        return "; ".join(strItems)
    
    def _fmt(self, pos):
        """Return position formatted as a string"""
        if pos == None:
            return "NaN"
        return self.posFmt % (pos,)
    
    def __eq__(self, rhs):
        """Return True iff position, status and finalPos are the same (ignores timestamp)"""
        return (self.pos == rhs.pos) \
            and (self.status == rhs.status)


class ActuatorFullInfo(ActuatorBasicInfo):
    """Full information for an actuator"""

    def __init__(self, name, posType, posFmt, speed, accel=None):
        """Create new object.
        
        Inputs
        - name      name of actuator; used for formatted output (case adjusted accordingly)
        - posType   type of position (typically int or float)
        - posFmt    format string for position (e.g. "%0.1f");
                    if None then a default is chosen based on posType
        - speed     maximum speed in units-of-position/second
        - accel     fixed acceleration in units-of-position/second^2;
                    if omitted or None then acceleration is infinite
        
        Speed and acceleration are used to predict motion time.
        
        Warning: __eq__ (==) only tests the basic fields.
        """
        ActuatorBasicInfo.__init__(self, name, posType, posFmt)
        self.posFmt = posFmt
        self.speed = abs(float(speed))
        self.accel = abs(float(accel)) if accel != None else None
        self.desPos = None
        self.startPos = None
        self.startTime = None
        self.predSec = None # predicted duration of move (in seconds)
    
    def startMove(self, desPos):
        """Call when starting a move to update the appropriate fields.
        
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
    
    def hubFormat(self):
        """Return status string formatted in hub key=value format"""
        # if moving then one output, otherwise another
        strItems = [
            ActuatorBasicInfo.hubFormat(self),
            "Des%s=%s" % (self.name, self._fmt(self.desPos)),
        ]
        if self.timestamp != None:
            if self.isMoving():
                elapsedSec = time.time() - self.startTime
                strItems += [
                    "%sPredTotalSec=%0.1f" % (self.name, self.predSec),
                    "%sElapsedSec=%0.1f" % (self.name, elapsedSec),
                ]
            else:
                strItems.append("%sError" % (self.name, self._fmat(self.pos - self.desPos)))
        return "; ".join(strItems)
        

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
    _CtrllrStatusRE = re.compile(r"(?P<piston>\d+\.\d+)\s+(?P<filter>\d+)\s+(?:\d+)\s+(?P<pistonStatus>\d+)\s+(?P<filterStatus>\d+)")
    _CharsToStrip = "".join([chr(n) for n in xrange(33)]) # control characters and whitespace
    def __init__(self, callFunc=None):
        TclActor.TCPDevice.__init__(self,
            name = "gmech",
            addr = ControllerAddr,
            port = ControllerPort,
            sendLocID = False,
            callFunc = callFunc,
        )
        self.statusID = None # "after" ID of next status command
        self.statusTime = None # time of most recently received status
        # dictionary of actuator (piston or focus): actuator status
        self.actuatorBasicStatusDict = {}
        for actArgs in ActuatorKArgs:
            self.actuatorBasicStatusDict[actArgs["name"]] = ActuatorBasicInfo(**actArgs)
        self.currCmd = None
        self.reqNReplies = 0 # number of replies wanted by this comand, including echo
        self.nReplies = 0 # number of replies read for current command, including echo
        self.currCmdTimer = None # ID of command timeout timer
        self.pendingCmd = None # only used to cancel REMAP
        self._tk = Tkinter.Frame()
    
    def getActuatorBasicInfoStr(self, actuatorStatus):
        # note: order of severity is 0, 1, 2... so just plow through the bits in order
        for bit in range(self.MaxActuatorBit):
            bitSet = (actuatorStatus >> bit) & 0x1
            if bitSet:
                return ActatorBitDict[bitSet]
        return ""
    
    def devConnStateCallback(self, devConn):
        """Called when a device's connection state changes."""
        TclActor.TCPDevice.devConnStateCallback(self, devConn)
        if self.devConn.connected():
            self.queryStatus()
        else:
            self.cancelQueryStatus()
    
    def cancelQueryStatus(self):
        """Cancel background status query, if any"""
        if self.statusID:
            self._tk.after_cancel(statusID)
            self.statusID = None
    
    def queryStatus(self):
        """Query status at regular intervals"""
        self.cancelQueryStatus()
        if not (self.currCmd or self.pendingCmd):
            # not busy; go ahead and request status
            statusCmd = TclActor.DevCmd("STATUS")
            self.startCmd(statusCmd)
        self.statusID = self._tk.after(queryStatus, StatusIntervalMS)
    
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
                statusMatch = self._CtrllrStatusRE.match(replyStr)
                if not statusMatch:
                    self.currCmd.setState("failed", "Could not parse reply %r" % (replyStr,))
                actuatorBasicStatusDict = statusMatch.groupdict()
                for act in ("piston", "focus"):
                    self.actuatorBasicStatusDict[act].set(
                        pos = actuatorBasicStatusDict[act],
                        status = actuatorBasicStatusDict["%sStatus" % (act,)],
                    )
            elif self.currCmd.cmdVerb == "REMAP":
                pass
            else:
                # only REMAP or STATUS should get any replies
                self.currCmd.setState("failed", "Unexpected reply %r" % (replyStr,))
        
        if isDone:
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
    
    def cmdDone(self, cmd):
        if not cmd.isDone():
            return
        if cmd == self.currCmd:
            self.setCurrCmd(None)
        else:
            print "Bug: GMechActor.cmdDone got command callback but command was not current command!"
        if self.pendingCmd:
            pendingCmd = self.pendingCmd
            self.pendingCmd = None
            self.startCmd(pendingCmd)
    
    def cmdTimeout(self, cmd):
        if self.currCmd != cmd:
            print "Warning: command time expired but command has changed"
            return
        self.currCmd.setState("failed", "Timed out")

    def startCmd(self, cmd):
        """Start a gmech controller command"""
        print "GMechDev.startCmd(%s)" % (cmd,)
        cmd.locID = 0
        if self.currCmd:
            print "there is an existing command %s" % (self.currCmd.cmdStr,)
            if self.currCmd.cmdVerb == "REMAP" and cmd.cmdVerb() == "INIT":
                if self.pendingCmd: # cancel command exists
                    cmd.setState("failed", "Busy cancelling REMAP")
                    return
                self.pendingCmd = cmd
                self.currCmd.setState("cancelling")
                self.conn.writeLine("") # send any character to cancel a REMAP
            else:
                cmd.setState("failed", "Busy executing %s" % self.currCmd.cmdVerb)
        else:
            print "writing to device: %r" % (cmd.cmdStr,)
            if cmd.cmdVerb == "REMAP":
                timeLimitMS = None
            else:
                timeLimitMS = 2000
            self.setCurrCmd(cmd, timeLimitMS)
            cmd.addCallback(self.cmdDone)
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
            devs = GMechDev(callFunc=self.updateCtrllrState),
        )
        self.ctrllr = self.devNameDict["gmech"]
        self.activeCmdDict = {} # dict of cmdVerb: userCmd
        self.actuatorFullStatusDict = dict() # dict of actuator: last-reported full status
        for actArgs in ActuatorKArgs:
            self.actuatorFullStatusDict[actArgs["name"]] = ActuatorFullInfo(**actArgs)
    
    def cancelSameCmd(self, newCmd):
        """Cancel a command of the same verb, if present"""
        cmdToCancel = self.activeCmdDict.get(newCmd.cmdVerb)
        if cmdToCancel:
            cmdToCancel.setState("cancelled", "superseded by %r" % (newCmd.cmdStr,))
    
    def checkLocalCmd(self, newCmd):
        """Check if a new local command can run given what else is going on.
        If not then raise TclActor.ConflictError(reason).
        If it can run but an existing command must be superseded then supersede the old command here.

        Note that each cmd_foo method can perform additional checks and cancellation.
        """
        if not self.activeCmdDict:
            return
        if "init" in self.activeCmdDict:
            raise TclActor.ConflictError("Busy running init")
        if "status" in self.activeCmdDict:
            raise TclActor.ConflictError("Busy running status")
            return
        if "remap" in self.activeCmdDict and newCmd.cmdVerb != "init":
            raise TclActor.ConflictError("Busy running remap (use init to cancel)")
    
    def updateCtrllrState(self, dev):
        """Called whenever the state of the gmech device changes"""
        # print status if needed
        statusCmd = self.activeCmdDict.get("status", TclActor.NullCmd)
        for actuator, fullStatus in self.actuatorFullStatusDict.iteritems():
            if statusCmd or (fullStatus != dev.actuatorBasicStatusDict[actuator]):
                # report status
                userID = statusCmd.userID if statusCmd else 0
                cmdID = statusCmd.cmdID if statusCmd else 0
                isOK = fullStatus.isOK()
                msgCode = ":" if isOK else "w"
                statusStr = fullStatus.hubFormat()
                self.writeToUsers(userID, cmdID, msgCode, statusStr)
                
                # update the basic status information
                self.actuatorFullStatusDict[actuator].copy(dev.actuatorBasicStatusDict[actuator])

        # if a move finished then report success or failure
        for actuator, fullStatus in self.actuatorFullStatusDict.iteritems():
            moveCmd = self.activeCmdDict.get("piston")
            if not moveCmd or fullStatus.finalPos == None:
                continue
            if fullStatus.isOK():
                moveCmd.setState("done")
            else:
                stateStr = dev.getActuatorBasicInfoStr(dev.pistonStatus)
                moveCmd.setState("failed", stateStr)
    
    def startDevCmd(self, devCmdStr, userCmd=None):
        """Send a command string to the controller.
        If userCmd is specified then it will track the device command
        (i.e. when the device command finishes or fails then so does the user command).
        """
        print "startDevCmd(%s)" % (devCmdStr)
        devCmd = TclActor.DevCmd(devCmdStr)
        if userCmd:
            userCmd.trackCmd(devCmd)
        self.ctrllr.startCmd(devCmd)

    def cmd_status(self, cmd=TclActor.NullCmd):
        """Return status"""
        self.checkNoArgs(cmd)
        self.startDevCmd("STATUS", cmd)
    
    def cmd_filter(self, cmd=TclActor.NullCmd):
        """Set the NA2 guider filter number"""
        filter = int(cmd.cmdArgs)
        devCmdStr = "FILTER %d" % (filter,)
        self.cancelSameCmd(cmd)
        self.startDevCmd(devCmdStr)
    
    def cmd_init(self, cmd=TclActor.NullCmd):
        """Initialize the NA2 guider mechanical controller and this actor"""
        self.checkNoArgs(cmd)
        for cmdVerb in self.actuatorFullStatusDict:
            cmdToCancel = self.activeCmdDict.get(cmdVerb)
            if cmdToCancel:
                cmdToCancel.setState("cancelled", "superseded by %r" % (cmd.cmdStr,))
        self.startDevCmd("INIT", cmd)

    def cmd_piston(self, cmd=TclActor.NullCmd):
        """Set the NA2 guider piston in um"""
        piston = float(cmd.cmdArgs)
        devCmdStr = "PISTON %0.1f" (piston,)
        self.cancelSameCmd(cmd)
        self.startDevCmd(devCmdStr)
    
    def cmd_remap(self, cmd=TclActor.NullCmd):
        """Remap actuators and reset controller"""
        self.checkNoArgs(cmd)
        self.startDevCmd("REMAP", cmd)


if __name__ == "__main__":
    import Tkinter
    root = Tkinter.Tk()
    b = GMechActor()
    root.mainloop()
