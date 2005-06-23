import hub

def startAllConnections(names=[]):
    """ Create all default connections, as defined by the proper configuration file. """

    for n in names:
        hub.startNub(n)
    
hub.init()
startAllConnections(['client',
                     'ping',
                     'TUI',
                     'tcc', 
                     'dcamera','dcam',
                     'gcamera','gcam',
                     'ecamera','ecam',
                     'tcc2gcam','tcc2ecam',
                     'disExpose', 'dis',
                     'nicfpsExpose', 'nicfps',
                     'echelleExpose', 'echelle',
                     ])
hub.run()
