#!/usr/local/bin/python
"""Base classes for interface to devices controlled by the Tcl Actor

To do:
- Add support for help strings associated with the list of commands handled by the device.
"""
__all__ = ["Device", "TCPDevice"]

#import RO.AddCallback
from RO.StringUtil import quoteStr
import RO.Comm.TCPConnection

class Device(RO.AddCallback.BaseMixin):
    """Device interface.
    
    Data includes information necessary to connect to this device
    and a list of commands handled directly by this device.
    
    Tasks include:
    - Send commands to the device
    - Parse all replies and use that information to:
      - Output appropriate data to the users
      - Upate a device model, if one exists
      - Call callbacks associated with the command, if any

    Inputs:
    - name  a short name to identify the device
    - conn  a connection to the device; the connection must support the following methods:
            - connect, disconnect, addReadCallback, addStateCallback, write, read, readLine
    - cmds  a list of command verbs for commands that should be sent
            directly through to this device
    - sendLocID prefix sent commands with the local id number?
    - callFunc  function to call when state of device changes;
                note that it is NOT called when the connection state changes;
                register a callback with "conn" for that task.
    - actor actor that contains this device; this gives access to writeToUsers
    """
    def __init__(self,
        name,
        conn,
        cmds = None,
        sendLocID = True,
        callFunc = None,
        actor = None,
    ):
        RO.AddCallback.BaseMixin.__init__(self)
        self.name = name
        self.cmds = cmds or()
        self.connReq = (False, None)
        self.conn = conn
        self.pendCmdDict = {} # key=locCmdID, value=cmd
        self.sendLocID = sendLocID
        self.actor = actor
        if callFunc:
            self.addCallback(callFunc, callNow=False)        
    
    def handleReply(self, replyStr):
        """Handle a line of output from the device.
        Inputs:
        - replyStr  the reply, minus any terminating \n
        
        Called whenever the device outputs a new line of data.
        
        This is the heart of the device interface and what makes
        each device unique. As such, it must be specified by the subclass.
        
        Tasks include:
        - Parse the reply
        - Manage pending commands
        - Update the device model representing the state of the device
        - Output state data to users (if state has changed)
        - Call the command callback
        
        Warning: this must be defined by the subclass
        """
        raise NotImplementedError()

    def sendCmd(self, cmd, cmdStr=None, callFunc=None):
        """Send a command to the device"""
        if cmd.locCmdID:
            self.pendCmdDict[cmd.locCmdID] = cmd
        if cmdStr == None:
            cmdStr = cmd.cmdStr
        if self.sendLocID:
            cmdStr = " ".join((str(cmd.locCmdID), cmdStr))
        try:
            print "Device.sendCmd writing %r" % (cmdStr,)
            self.conn.writeLine(cmdStr)
        except Exception, e:
            quotedErr = quoteStr(str(e))
            quotedCmd = quoteStr(cmdStr)
            cmd.setState(isDone=True, isOK=False, reason=str(e))


class TCPDevice(Device):
    """TCP-connected device.
    
    Inputs:
    - name  a short name to identify the device
    - addr  IP address
    - port  port
    - cmds  a list of command verbs for commands that should be sent
            directly through to this device
    - sendLocID prefix sent commands with the local id number?
    - callFunc  function to call when state of device changes;
                note that it is NOT called when the connection state changes;
                register a callback with "conn" for that task.
    """
    def __init__(self,
        name,
        addr,
        port = 23,
        cmds = None,
        sendLocID = True,
        callFunc = None,
        actor = None,
    ):
        Device.__init__(self,
            name = name,
            cmds = cmds,
            conn = RO.Comm.TCPConnection.TCPConnection(
                host = addr,
                port = port,
                readCallback = self._readCallback,
                readLines = True,
            ),
            sendLocID = sendLocID,
            callFunc = callFunc,
            actor = actor,
        )
    
    def _readCallback(self, sock, replyStr):
        """Called whenever the device has returned a reply.
        Inputs:
        - sock  the socket (ignored)
        - line  the reply, missing the final \n     
        """
        print "TCPDevice._readCallback(sock, replyStr=%r)" % (replyStr,)
        self.handleReply(replyStr)
