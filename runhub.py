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
startAllConnections(['client',
                     'ping',
                     'TUI','cmdinauth',
                     'tcc', 
                     'tcamera','tcam',
                     'dcamera','dcam',
                     'gcamera','gcam',
                     'ecamera','ecam',
                     'tcc2gcam','tcc2ecam',
                     'disExpose', 'dis',
                     'nicfpsExpose', 'nicfps',
                     'echelleExpose', 'echelle',
                     'spicam','spicamExpose', "sfocus",
                     'tspec', 'tspecExpose',
                     'nfake', 'nfocus',
                     'cmiccServer', 'cm',
                     'telmech', 'gmech',
                     ])

# Manually add TS01 as an always-active commander of apollo.
g.perms.addPrograms(['TS01'])
g.perms.addActors(['tspec', 'tcam'])
g.perms.addActorsToProgram('TS01', ['tspec','tcam'])

# Manually add ZA01 as an always-active commander of apollo.
g.perms.addPrograms(['ZA01'])
g.perms.addActors(['apollo'])
g.perms.addActorsToProgram('ZA01', ['apollo'])

# Instrument monitoring, echelle
g.perms.addPrograms(['MN01'])
g.perms.addActors(['echelle'])
g.perms.addActors(['telmech'])
g.perms.addActors(['tspec'])
g.perms.addActorsToProgram('MN01', ['tcc', 'echelle', 'telmech', 'tspec'])

hub.run()
