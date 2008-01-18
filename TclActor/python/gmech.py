#!/usr/local/bin/python
"""gmech actor

TO DO:
- Document keywords: Superseded, Timeout, Cmd
- No status at user connect time. Why?
- No status reported at device connect time. Why?
- "piston 56" makes the controller upset; it NEEDS a decimal point.
  Either make it an actor command or coerce all arguments for motion commands.
  I prefer the latter, I think. But it limits the user's ability to send arbitrary text to the ctrllr.
- Superseding motion commands seems to be broken. Once the controller got upset
  as per above then sending a new motion command did not make it happy again.
  I got a lot of this sort of thing:
  GMechDev.handleReply: replyStr='20002.50 0 51618.000  48  48 OK'; nReplies=1
TkSocket sock12 read callback <bound method TCPConnection._sockReadLineCallback of <RO.Comm.TCPConnection.TCPConnection object at 0x10e46d0>> failed: Command is done; cannot change state
Traceback (most recent call last):
  File "/Library/Frameworks/Python.framework/Versions/2.5/lib/python2.5/site-packages/RO-2.2.5b1-py2.5.egg/RO/Comm/TkSocket.py", line 482, in _doRead
    self._readCallback(self)
  File "/Library/Frameworks/Python.framework/Versions/2.5/lib/python2.5/site-packages/RO-2.2.5b1-py2.5.egg/RO/Comm/TCPConnection.py", line 356, in _sockReadLineCallback
    subr(sock, dataRead)
  File "/Users/rowen/Instruments/tron trunk/TclActor/python/TclActor/Device.py", line 143, in _readCallback
    self.handleReply(replyStr)
  File "gmech.py", line 353, in handleReply
    cmd = self.currCmd,
  File "gmech.py", line 185, in setStatus
    self.moveCmd.setState("done")
  File "/Users/rowen/Instruments/tron trunk/TclActor/python/TclActor/Command.py", line 69, in setState
    raise RuntimeError("Command is done; cannot change state")
  RuntimeError: Command is done; cannot change state
How could a move command end and still be stuck in self.moveCmd???

  
- Make INIT more robust by retrying if the first one fails.
  This would clear out the typeahead buffer, for instance.
  I suspect that instead of tying device command INIT to user command init
  it makes more sense to have a special "init" method for the device.
- Measure actual speed and acceleration and set ActuatorModel.ActuatorInfo accordingly.
  This would probably be most accurately determined by printing elapsed time for various moves
  (but keep in mind the polling granularity).
- Parse REMAP replies (or if none expected then eliminate them).
- Test command queueing and collision handling as thoroughly as possible;
  it is complicated and it would be best to test all branches of the code
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
    # actuator info is a dict of name: (posType, posFmt, speed, accel)
    ActuatorInfo = dict(
        piston = (float, "%0.2f", 1.0, 1.0),
        filter = (int,   "%0d",   0.1, 1.0),
    )
    def __init__(self, name, writeToUsersFunc):
        actInfo = self.ActuatorInfo.get(name)
        if not actInfo:
            raise RuntimeError("Unknown actuator %r" % (name,))
        self.name = name.title()
        self.posType, self.posFmt, self.speed, self.accel = actInfo
        self.writeToUsersFunc = writeToUsersFunc
        
        # items read from status
        self.statusTimestamp = None
        self.pos = None
        self.status = None
        
        # items from a move command
        self._clearMove()
    
    def cancelMove(self, msg="Superseded"):
        """Mark the current motion command (if any) as cancelled.
        Warning: this does not communicate with the controller!
        """
        if self.moveCmd:
            self.moveCmd.setState("cancelled", hubMsg="Superseded")
        self._clearMove()
    
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
        msgCode = ":" if self.isOK() else "w"
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
        try:
            desPos = self.posType(moveCmd.cmdArgs)
            moveCmd.cmdArgs = self.posFmt % (desPos,)
            moveCmd.cmdStr = ("%s %s" % (moveCmd.cmdVerb, moveCmd.cmdArgs))
        except Exception, e:
            moveCmd.setState("failed", textMsg="Could not parse position %r" % (moveCmd.cmdArgs),
                hubMsg="Exception=%s" % (quoteStr(str(e)),))
            raise RuntimeError(e)
            
        moveCmd.addCallback(self.updMoveCmdState)

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
                rampDist = self.speed / self.accel
                if dist <= rampDist:
                    self.predSec = 2.0 * math.sqrt(dist / self.accel)
                else:
                    rampTime = 2.0 * self.speed / self.accel
                    self.predSec = rampTime + ((dist - rampDist) / self.speed)
    
    def updMoveCmdState(self, cmd):
        """Callback function for move commands"""
        if cmd.isDone():
            self._clearMove()

    def setStatus(self, pos, status, cmd=None):
        """Set status values."""
        #print "ActuatorModel.setStatus(pos=%s, status=%s)" % (pos, status)
        pos = self.posType(pos)
        status = int(status)
        statusChanged = (pos != self.pos) or (status != self.status)
        self.statusTimestamp = time.time()
        self.pos = pos
        self.status = status
        if statusChanged or (cmd and cmd.userID != 0):
            msgCode, statusStr = self.hubFormat()
            self.writeToUsersFunc(msgCode, statusStr, cmd=cmd)
        
        if self.moveCmd and not self.isMoving():
            if self.isOK():
                self.moveCmd.setState("done")
            else:
                self.moveCmd.setState("failed", textMsg="Bad actuator status")
    
    def _clearMove(self):
        """Clear all move command information.
        """
        self.moveCmd = None
        self.startTime = None
        self.desPos = None
        self.predSec = None # predicted duration of move (in seconds)
    
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
            sendLocID = False,
            callFunc = callFunc,
            actor = actor,
            cmdInfo = (
              ("init",   None, "initialize the gmech controller"),
              ("remap",  None, "remap the piston and filter actuators and reset the gmech controller"),
              ("piston", None, "um: set the guider piston (focus)"),
              ("filter", None, "filtnum: set the guider filter"),
              ("status", None, "return gmech controller status")
            ),
        )
        self.queryStatusTimer = None # "after" ID of next queryStatus command
        # dictionary of actuator (piston or filter): actuator status
        self.actuatorStatusDict = {}
        for actName in ActuatorModel.ActuatorInfo.keys():
            self.actuatorStatusDict[actName] = ActuatorModel(actName, self.actor.writeToUsers)
        self.cmdQueue = []
        self.currCmd = None
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
        if self.queryStatusTimer:
            self._tk.after_cancel(self.queryStatusTimer)
            self.queryStatusTimer = None
    
    def queryStatus(self):
        """Query status at regular intervals.
        """
        print "queryStatus"
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
            statusCmd = TclActor.DevCmd("STATUS")
            self.newCmd(statusCmd)
        
        isMoving = False
        for actStatus in self.actuatorStatusDict.itervalues():
            isMoving = isMoving or actStatus.moveCmd
        intervalMS = StatusIntervalMovingMS if isMoving else StatusIntervalHaltedMS
        #print "isMoving=%s, intervalMS=%s" % (isMoving, intervalMS)
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
                        
            elif self.currCmd.cmdVerb == "REMAP":
                # probably should parse this data, but for now just spit it out...
                self.actor.writeToUsers("i", "RemapData=%s" % (quoteStr(replyData)), cmd=self.currCmd)
            else:
                # only REMAP or STATUS should get any replies
                self.currCmd.setState("failed", textMsg="Unexpected reply %r" % (replyStr,))
        
        if isDone and self.currCmd:
            if self.nReplies < 1:
                self.currCmd.setState("failed", textMsg="No command echo")
            else:
                # if actuator command then mark as started
                actStatus = self.actuatorStatusDict.get(self.currCmd.cmdVerb.lower())
                if actStatus:
                    # an actuator move; print "started", remove from self.currCmd
                    # and start next command (if any)
                    self.writeToUsers("i", "Started", self.currCmd)
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
        print "startCmd %s; currCmd=%s; currCmdTimer=%s" % (cmd, self.currCmd, self.currCmdTimer)
        if self.currCmd or self.currCmdTimer:
            raise RuntimeError("Current command and/or command timer exists")

        # if this is an actuator move then vet the arguments and set actuator status
        isMove = False
        actStatus = self.actuatorStatusDict.get(cmd.cmdVerb.lower())
        if actStatus:
            # this is an actuator move
            isMove = True
            try:
                actStatus.setMove(cmd)
            except RuntimeError, e:
                print "Move rejected: %s" % (e,)
                pass

        self.currCmd = cmd
        if timeLimitMS:
            self.currCmdTimer = self._tk.after(timeLimitMS, self.cmdTimeout, cmd)
        cmd.addCallback(self.cmdCallback)
        self.conn.writeLine(cmd.cmdStr)

        if isMove:
            # query status right after the move starts
            self.queryStatus()
    
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

    def newCmd(self, cmd):
        """Submit a new command"""
        print "GMechDev.newCmd(%s)" % (cmd,)
        if not self.conn.isConnected():
            raise RuntimeError("Device %s is not connected" % (self.name,))
            
        # enforce proper case
        cmd.cmdStr = cmd.cmdStr.upper()
        cmd.cmdVerb = cmd.cmdVerb.upper()
        cmd.cmdArgs = cmd.cmdArgs.upper()

        if self.currCmd:
            # queue up the command unless the existing command is remap
            if cmd.cmdVerb == "INIT":
                # clear the command queue and replace with this init command
                for actStatus in self.actuatorStatusDict.itervalues():
                    actStatus.cancelMove("Superseded by init")
                for queuedCmd in self.cmdQueue:
                    queuedCmd.setState("cancelled", textMsg="Superseded by init", hubMsg="Superseded")
                self.cmdQueue = [cmd]
                
                # if REMAP is running cancel it (other commands run quickly and can't be cancelled)
                if self.currCmd.cmdVerb == "REMAP":
                    self.conn.writeLine("") # start cancelling REMAP
                    self.currCmd.cmdVerb.setState("cancelled", textMsg="Superseded by init", hubMsg="Superseded")
                return

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
        self.ctrllr = self.devNameDict["gmech"]
        self.moveCmdDict = {} # dict of cmdVerb: userCmd for actuator moves
    
    def newUserOutput(self, userID, tkSock):
        """Report status to new user"""
        for actuator, actStatus in self.ctrllr.actuatorStatusDict.iteritems():
            msgCode, statusStr = actStatus.hubFormat()
            self.writeToOneUser(msgCode, statusStr, userID=userID)


if __name__ == "__main__":
    import Tkinter
    root = Tkinter.Tk()
    b = GMechActor()
    root.mainloop()
