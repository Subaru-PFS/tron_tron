import hub

def startAllConnections(names=[]):
    """ Create all default connections, as defined by the proper configuration file. """

    for n in names:
        hub.startNub(n)
    
hub.init()
startAllConnections(['client', 'TUI', 'tcc', 'cm', 'cmiccServer'])
hub.run()
