import socket
import sys

class GimCtrlConnection(object):
    """ Encapsulate a control connection to a GimCtrl Mac.
    
    - The Mac in on a terminal server (this might chage to a socket).
    - Commands to the Mac are single lines of text.
    - Responses are 0 or more lines of text, terminated by the line " OK"
    - We are the only command source.
    
    """

    def __init__(self, host, port):
        """ Establish the connection to a socket """

        # We might not read entire lines, which are what the caller gets.
        # So pile data up.
        self.buffer = ""

        self.EOL = '\r\n'
        
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((host, port),)

    def sendCmd(self, cmdString, timeout):
        """ Send a command and wait for the entire response.

        Args:
           cmdString - unterminated command string.
           timeout   - How long to wait -- in total -- for the command to complete.
                       Specify None to wait forever.
        """

        self.timeout = timeout
        self.s.settimeout(timeout)

        sys.stderr.write("======== GimCtrl sending: %s\n" % (cmdString))
        self.s.send(cmdString + self.EOL)

        buffer = ""
        while 1:
            try:
                ret = self.s.recv(50000)
            except Exception, e:
                raise RuntimeError("sendCmd timed out: %s" % (e))
            
            sys.stderr.write("======== GimCtrl got: %r\n" % (ret))
            buffer += ret
            if buffer[-7:] == "\r\n OK\r\n":
                break

        # We want the OK to be the last line.
        tlines = buffer.split("\r\n")[:-1]

        # Some lines have spurious leading \ns:
        lines = []
        for l in tlines:
            lines.append(l.replace('\n', ''))

        return lines
    
    
