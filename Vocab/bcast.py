__all__ = ['bcast']

import time

import CPL
import Hub
import Vocab.InternalCmd as InternalCmd

""" A variant on instant messaging, where a Commander can inject keywords.

    The single command is:
        bcast BID name flag [keys]
    
    which injects the keys as coming from the given name with the MID BID

    bcast.name BID cmdrID flag keys
    
"""
class bcast(InternalCmd.InternalCmd):

    def __init__(self, **argv):
        InternalCmd.InternalCmd.__init__(self, 'bcast', **argv)
        self.decoder = Hub.ASCIIReplyDecoder(CIDfirst=True, debug=9)
        
    def sendCommand(self, cmd):
        """ Generate a Reply from the given pseudo-Command.

        cmd must have three arguments:
          - a name, which sets part of the Reply's "actor"
          - an MID to assign to the "Command"
          - a reply flag. e.g, i,w,:

        and may have other arguments, which must parse as a protocol reply. i.e.
        a semicolon-delimited list of key variables.

        Hmm, maybe the ID should be 
        """

        # One interesting thing about this command is that all its arguments are
        # constructed to look like a _Reply_ instead of a command. So we use a different parser
        # from other hub words.
        #
        # What do we need to do?
        #  1) Parse the "command" line as a reply
        #
        s = cmd.cmd
        s.strip()
        s = "%s.%s\n" % ('bcast', s)
        r, leftover = self.decoder.decode(s, None)
        if not r:
            cmd.fail('bcastTxt="could not parse command line"')
            return
        if leftover:
            cmd.fail('bcastTxt=%s' % (CPL.qstr("could not completely parse command line. Leftovers=%s" % (leftover))))
            return

        #  2) Construct a pseudo-Command to go with it.
        c = Hub.Command(cmd.cmdrName, cmd.cmdrName, r['mid'], r['cid'], '', bcastCmdInfo=False)

        #  3) Fire it.
        c.addReply(r)

        cmd.finish('')

        
    
