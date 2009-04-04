__all__ = ['TCCShellNub']

import CPL
import Hub.Reply
from ShellNub import ShellNub

class TCCShellNub(ShellNub):
    """ An ShellNub with the plumbing required to recognize and record the TCC YourUserName as
        our .cid.
    """

    def findUserNum(self, kvl):
        """ Find YourUserNum key in list of KVs. Return the CID or None. """
        
        for k, v in kvl.iteritems():
            if k == "YourUserNum":
                cid = int(v[0])
                return cid
        return None
    
    def copeWithInput(self, s):
        """ Override the default copeWithInput to set our .cid from the YourUserNum key. """
        
        if self.debug > 5:
            CPL.log('TCCShell.copeWithInput', "Nub %s read: %r, with buf=%r" % (self.name, s, self.inputBuffer))

        while 1:
            # Connections to the TCC's tccuser captive account return lines
            # terminated by CRLF, but with the LF coming at the start of the "next
            # line". Odd, and to be investigated. In the meanwhile, strip leading LFs
            #
            if len(self.inputBuffer) > 0 and self.inputBuffer[0] == '\n':
                self.inputBuffer = self.inputBuffer[1:]
                
            reply, leftover = self.decoder.decode(self.inputBuffer, s)
            s = None
            if self.debug > 5:
                CPL.log('TCCShell.copeWithInput', "decoded: %s, yielding buf=%r" % (reply, leftover))

            self.inputBuffer = leftover
            if not reply:
                break

            if self.log:
                try:
                    txt = reply['RawText']
                except:
                    txt = "UNKNOWN INPUT"
                self.log.log(txt, note='<')
            
            # Here's the special TCC bit: search for YourUserNum, 
            if self.cid == None:
                newCID = self.findUserNum(reply['KVs'])
                if newCID != None:
                    self.cid = newCID
                    CPL.log('TCCShell.copeWithInput', "setting CID=%s" % (self.cid))
                    self.connected()
                    
            cmd = self.getCmdForReply(reply)
            r = Hub.Reply.Reply(cmd, reply['flag'], reply['KVs'])
            cmd.reply(r)
        
