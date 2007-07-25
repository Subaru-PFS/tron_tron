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
            g.hubcmd.warn('text=%s' % (CPL.qstr('FAILED to start nub %s: %s\n', n, e)))
    
hub.init()
startAllConnections(['client',
                     'ping',
                     'TUI','cmdinauth',
                     'tcc', 
                     'dcamera','dcam',
                     'gcamera','gcam',
                     'ecamera','ecam',
                     'tcc2gcam','tcc2ecam',
                     'disExpose', 'dis',
                     'nicfpsExpose', 'nicfps',
                     'echelleExpose', 'echelle',
                     'spicam','spicamExpose', "sfocus",
                     'nfake', 'nfocus',
                     'cmiccServer', 'cm',
                     'telmech'
                     ])

# Manually add ZA01 as an always-active commander of apollo.
g.perms.addPrograms(['ZA01'])
g.perms.addActors(['apollo'])
g.perms.addActorsToProgram('ZA01', ['apollo'])

# Instrument monitoring, echelle
g.perms.addPrograms(['MN01'])
g.perms.addActors(['echelle'])
g.perms.addActors(['telmech'])
g.perms.addActorsToProgram('MN01', ['tcc', 'echelle', 'telmech'])

hub.run()
