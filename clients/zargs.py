#!/usr/bin/env python

import client
import Actor
import CPL

class ArgsActor(Actor.Actor):
    """ An oh-so-simple actor that merely prints out the parsed form of its command arguments.
    """

    def __init__(self, **args):
        Actor.Actor.__init__(self, 'zargs', **args)

        self.helpText = ("zargs arguments -- print parsed arguments.")
        
    def _parse(self, cmd):

        for k in cmd.argv:
            cmd.respond('key=%s; val=%s' % (CPL.qstr(k), CPL.qstr(cmd.argDict[k])))
        cmd.finish()

def main(name, actor=None, debug=0, test=False):
    if actor == None:
        actor = ArgsActor(debug=debug)
    actor.start()

    try:
        client.run(name=name, cmdQueue=actor.queue, background=False, debug=debug, cmdTesting=test)
    except SystemExit, e:
        CPL.log('%s.main' % (name), 'got SystemExit')
        raise
    except:
        raise

if __name__ == "__main__":
    main('zargs', debug=1)
    
