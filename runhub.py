#import pychecker
import hub

def startAllConnections(names=[]):
    """ Create all default connections, as defined by the proper configuration file. """

    for n in names:
        hub.startNub(n)
    
hub.init()
startAllConnections(['tcc',
                     'dis', 'disExpose',
                     'grim', 'grimExpose',
                     'echelle', 'echelleExpose',
                     'cm', 'cmiccServer',
                     'client', 'cmdin', 'TUI'])
hub.run()
