import sys

import CPL
import g
import hub

def startAllConnections(names):
    """ Create all default connections, as defined by the proper configuration file. """

    for n in names:
        try:
            hub.startNub(n)
        except Exception, e:
            sys.stderr.write("FAILED to start nub %s: %s\n" % (n, e))
            try:
                g.hubcmd.warn('text=%s' % (CPL.qstr('FAILED to start nub %s: %s\n', n, e)))
            except:
                sys.stderr.write("hubcmd.warn failed\n")
    
hub.init()
startAllConnections(CPL.cfg.get('hub', 'nubs', doFlush=True))

hub.run()
