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
#                     'gcamera', 'ecamera',
                     'tcc2ecam', 'tcc2gcam',
#                     'ecam',
#                     'gcam',
                     'disExpose', 'dis',
                     'nicfpsExpose', 'nicfps',
#                     'echelleExpose', 'echelle',
                     ])
hub.run()
