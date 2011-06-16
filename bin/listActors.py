#!/usr/bin/env python

import os
import CPL.cfg

def getActors(actorName=None, hostName=None):
    # Bootstrap the whole configuration system
    configPath = os.environ.get('CONFIG_DIR',
                                os.path.join(os.environ['TRON_DIR'], 'config'))
    CPL.cfg.init(path=configPath, verbose=False)
    
    actors = CPL.cfg.get('hub', 'actors')
    if actorName:
        actors = dict([(key, val) for key, val in actors.items() if key == actorName])
    if hostName:
        actors = dict([(key, val) for key, val in actors.items() if (hostName in (val['host'],
                                                                      val['host'].split('.', 1)[0]))])
    return actors

def printActors(actors, verbose=False):
    if verbose:
        actorList = ["%s,%s,%s" % (actors[name]['actorName'],
                                   actors[name]['host'],
                                   actors[name]['port']) for name in actors.keys()]
    else:
        actorList = [actors[name]['actorName'] for name in actors.keys()]

    if actorList:
        print "\n".join(actorList)

def main():
    printActors(getAllActors())

if __name__ == "__main__":
    from optparse import OptionParser
    
    parser = OptionParser()
    parser.add_option("-H", "--host", dest="hostName", default=None,
                      help="match actors on given host", metavar="HOST")
    parser.add_option("-n", "--name", dest="actorName", default=None,
                      help="match given actor", metavar="ACTOR")
    parser.add_option("-v", "--verbose", action='store_true',
                      dest="verbose", default=False,
                      help="print all actor fields")

    (options, args) = parser.parse_args()

    actors = getActors(actorName=options.actorName,
                       hostName=options.hostName)
    printActors(actors, verbose=options.verbose)


    
