import hub

def startAllConnections(names=[]):
    """ Create all default connections, as defined by the proper configuration file. """

    for n in names:
        hub.startNub(n)
    
hub.init()
startAllConnections(['client', 'ping', 'tcc', 'TUI',
                     'tcc2ecam', 'tcc2gcam',
                     'ecam', 'gcam',
                     'disExpose', 'dis',
                     'nicfpsExpose', 'nicfps'])
hub.run()
