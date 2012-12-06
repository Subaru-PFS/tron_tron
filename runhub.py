import argparse
import sys

import g
import hub
import CPL

def startAllListeners(names):
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", help="configuration name, used to find subdirectory in $root/config/",
                        action="store", default='')
    args = parser.parse_args()
    
    hub.init(configName=args.config)
    startAllListeners(CPL.cfg.get('hub', 'listeners', doFlush=True))
    hub.run()

if __name__ == "__main__":
    main()
