#import pychecker
import hub

def startAllConnections(names=[]):
    """ Create all default connections, as defined by the proper configuration file. """

    for n in names:
        hub.startNub(n)
    
hub.init()
startAllConnections(['client',
                     'tcc',
                     'dis', 'disExpose',
                     'grim', 'grimExpose',
                     'echelle', 'echelleExpose',
                     'nicfps', 'nicfpsExpose',
                     'gcam', 'tcc2gcam',
                     'ecam', 'tcc2ecam',
                     'cmdin', 'TUI'])
hub.run()
