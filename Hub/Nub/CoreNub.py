__all__ = ['CoreNub']

import CPL

import IO
import hub

class CoreNub(IO.IOHandler):
    """ Base class for hub connections to the outside world.

    Because of the asymmetric nature of the protocol, each Nub must subclass from
    either CommanderNub or ActorNub, and not from CoreNub directly.
    
    - sendCommand(cmd)
    - sendReply(reply)
    - parseCommand(input)
    - parseReply(input)
    
    Each connection can/must be configured with specific:
       - input decoder  -- recognizes and extracts complete input chunks.
       - output encoder -- 
    """

    def __init__(self, poller, **argv):
        name = argv.get('name', None)
        self.ID = name
        self.name = name
        self.nubType = argv.get('type', 'unknown')
        self.needsAuth = argv.get('needsAuth', False)
        self.userInfo = None
        
        IO.IOHandler.__init__(self, poller, **argv)

        self.encoder = argv.get('encoder', None)
        self.decoder = argv.get('decoder', None)
        self.encoder.setNub(self.ID)
        self.decoder.setNub(self.ID)
        
        self.otherIP = argv.get('otherIP', None)
        self.otherFQDN = argv.get('otherFQDN', None)

        self.inputBuffer = ""
        self.outputBuffer = ""

        logDir = argv.get("logDir", None)
        if logDir:
            self.log = CPL.Logfile(logDir, EOL='', doEncode=True)
        else:
            self.log = None
            
    def __str__(self):
        return "CoreNub(id=%s, name=%s, type=%s)" % (self.ID, self.name, self.nubType)
    
    def setName(self, newName):
        """ Change our username(s). """

        self.name = newName
        self.encoder.setName(self.name)
        self.decoder.setName(self.name)

    def connected(self):
        pass
    
    def shutdown(self, **argv):
        """ Release all resources and shut down. 

        Args:
           notifyHub(True)     - call the hub rather than clean up ourselves.
           why('')             - i
           
        If called from "below" (i.e. a socket has been shutdown), just
        calls the hub's dropNub method, which will shortly call us back.
        
        If called from the hub, close all IO resources.
        """

        notifyHub = argv.get('notifyHub', True)
        why = argv.get('why', '')
        
        CPL.log("Hub.shutdown", "notify=%s why=%s" % (notifyHub, why))
        
        if notifyHub:
            hub.dropNub(self)
        else:
            self.ioshutdown(**argv)

    def flagFinishesCommand(self, f):
        """ Return True if a reply flag completes the command. """
        
        return f in ':fF'

    def statusCmd(self, cmd, doFinish=True):
        """ Send sundry status information keywords.
        """

        IO.IOHandler.statusCmd(self, cmd, self.name, doFinish=False)

        if doFinish:
            cmd.finish()
            
    
