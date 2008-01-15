#!/usr/local/bin/python
"""Base classes for interface to devices controlled by the Tcl Actor
"""
__all__ = ["Device", "TCPDevice"]

#import RO.AddCallback
from RO.StringUtil import quoteStr
import RO.Comm.TCPConnection

class Device(object):
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
    """
    def __init__(self,
        name,
        conn,
        cmds = None,
        sendLocID = True,
    ):
        self.name = name
        self.cmds = cmds or()
        self.connReq = (False, None)
        self.conn = conn
        self.pendCmdDict = {} # key=locCmdID, value=cmd
        self.writeToUsersFunc = None
        self.sendLocID = sendLocID
    
    def handleReply(self, replyStr):
        """Handle a line of output from the device.
        Inputs:
        - replyStr  the reply, minus any terminating \n
        
        Called whenever the device outputs a new line of data.
        
        This is the heart of the device interface and what makes
        each device unique. As such, it must be specified by the subclass.
        
        Tasks include:
        - Parse the reply
        - Manage the pending command dict
        - Output data to users
        - Maintain a device model (recommended but not required)
        - If a command has finished, call the appropriate command callback
        
        Warning: this must be defined by the subclass
        """
        raise NotImplementedError()

    def sendCmd(self, cmd, cmdStr=None, callFunc=None):
        """Send a command to the device"""
        if cmd.locID:
            self.pendCmdDict[cmd.locID] = cmd
        if cmdStr == None:
            cmdStr = cmd.cmdStr
        if self.sendLocID:
            cmdStr = " ".join((str(cmd.locID), cmdStr))
        try:
            self.conn.writeLine(cmdStr)
        except Exception, e:
            quotedErr = quoteStr(str(e))
            quotedCmd = quoteStr(cmdStr)
            self.writeToUsers(cmd.cmdID, cmd.userID, "f",
                "Exception=%s; Text=%s; CmdStr=%s" % (e.__class__.__name__, quotedErr, quotedCmd))
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
    """
    def __init__(self,
        name,
        addr,
        port = 23,
        cmds = None,
        sendLocID = True,
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
        )
    
    def _readCallback(self, sock, replyStr):
        """Called whenever the device has returned a reply.
        Inputs:
        - sock  the socket (ignored)
        - line  the reply, missing the final \n     
        """
        self.handleReply(replyStr)
