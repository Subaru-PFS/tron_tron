import hub

def startAllNubs(names=None):
    """ Create all default connections, as defined by the proper configuration file. """

    if names == None:
        names = ('cmdin', 'client', 'TUI', 'dis', 'tcc')
        
    for n in names:
        hub.startNub(n)
        

hub.init()
startAllNubs(['cmdin', 'client', 'TUI', \
              'tcc', 'dis', 'grim', 'echelle', \
              'echelleExpose', 'grimExpose', 'disExpose'])
hub.run()
