#!/usr/bin/env python

__all__ = ['GFake']

import os.path

import client
import Actor
import CPL
import GCamBase

class GFake(GCamBase.GCamBase, Actor.Actor):
    """
    Pretend to take images.
    """
    
    def __init__(self, name, **argv):
        """ Use an Alta camera. """
        
        Actor.Actor.__init__(self, name, **argv)
        GCamBase.GCamBase.__init__(self, name, **argv)

        self.commands.update({'status':     self.statusCmd,
                              'expose':     self.exposeCmd,
                              'init':       self.initCmd,
                              })

    def doCmdExpose(self, cmd, type, tweaks):
        """ Parse the exposure arguments and act on them.

        Args:
            cmd    - the controlling Command
            type   - 'object' or 'dark'
            tweaks - dictionary of configuration values.
            
        CmdArgs:
            usefile - an existing full path name.
                        If specified, the time,window,and bin arguments are ignored,
                        and the given file is simply returned.

        useFile MUST be specified.
        """

        matched, notMatched, leftovers = cmd.match([('usefile', cmd.qstr)])

        # Extra double hack: use a disk file instead of acquiring a new image
        if matched.has_key('usefile'):
            filename = matched['usefile']
            cmd.finish('camFile=%s' % (filename))
        else:
            cmd.fail('text="ncamera cannot actually expose, so the usefile argument MUST be specified"')
            

    def statusCmd(self, cmd, doFinish=True):
        """ Generate status keywords. Does NOT finish the command.
        """

        if doFinish:
            cmd.finish()
            

# Start it all up.
#
def main(name, debug=0, test=False):
    camActor = GFake('nfake', debug=debug)
    camActor.start()

    client.run(name=name, cmdQueue=camActor.queue,
               background=False, debug=debug, cmdTesting=test)
    CPL.log('ncamera.main', 'DONE')

if __name__ == "__main__":
    main('ncamera', debug=3)
