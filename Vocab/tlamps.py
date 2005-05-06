all = ['tlamps']

import os
import time

import CPL
import Vocab.InternalCmd as InternalCmd

""" Control the lamp controller.

    Commands:
       list
       on a b c
       off [a b]

    Keys:
       lampNames=a,b,c,d,e
       lampStates=0,0,1,0,0

"""
class tlamps(InternalCmd.InternalCmd):
    def __init__(self, **argv):
        argv['safeCmds'] = '^\s*(list|status)\s*$'
        argv['needsAuth'] = True
        InternalCmd.InternalCmd.__init__(self, 'tlamps', **argv)

        self.commands = { 'list' : self.doList,
                          'status' : self.doList,                          
                          'on' : self.doOn,
                          'off' : self.doOff,
                          }

        # The lamps names that we recognize.
        self.okLamps = ('1', '2', '3', '4', '5', '7', '8') # Not 6, yet.
        
        # How to control the lamp controller
        self.lampsCmd  = "ssh -1 -i /home/apotop/.ssh/mc arc@holecard bin/lamps"

    def _returnKeys(self, cmd, names=None, states=None):
        
        KVs = []
        if names:
            KVs.append('lampNames=%s' % (names))
        if states:
            KVs.append('lampStates=%s' % (states))

        cmd.finish('; '.join(KVs))
        
    def doList(self, cmd):
        """ Fetch the lamp names and states and return the proper keywords

        Keywords:

           lampNames=a,b,c,d,e
           lampStates=0,0,1,0,1
        """

        names, states = self._getLamps()
        self._returnKeys(cmd, names=names, states=states)

    def doOn(self, cmd):
        """ Turn some lamps on.

        Keywords:

           lampNames=a,b,c,d,e
           lampStates=0,0,1,0,1
        """

        lamps = cmd.cmd.split()
        lamps = lamps[1:]

        if len(lamps) == 0:
            cmd.fail('lampsTxt=%s' % (CPL.qstr("tlamps on needs to turn on at least one lamp...")))
            return
            
        for l in lamps:
            if not l in self.okLamps:
                cmd.fail('lampsTxt=%s' % (CPL.qstr("unknown lamp name: %s" % (l))))
                return
            
        states = self._doOn(lamps)
        self._returnKeys(cmd, states=states)

    def doOff(self, cmd):
        """ Turn some lamps off.

        Keywords:

           lampNames=a,b,c,d,e
           lampStates=0,0,1,0,1
        """

        lamps = cmd.cmd.split()
        lamps = lamps[1:]
        for l in lamps:
            if not l in self.okLamps:
                cmd.fail('lampsTxt=%s' % (CPL.qstr("unknown lamp name: %s" % (l))))
                return
            
        states = self._doOff(lamps)
        self._returnKeys(cmd, states=states)
        
    def _getLamps(self):
        """ Fetch the state of the lamps.

        Returns:
           - list of lamp names
           - list of lamp states
        """

        try:
            lampProg = os.popen('%s list' % (self.lampsCmd), 'r')
            names = lampProg.readline()
            states = lampProg.readline()
            lampProg.close()
        except:
            raise Exception("Failed to list the lamps")
        
        return names.strip(), states.strip()

    def _doOn(self, lamps):
        if len(lamps) == 0:
            return self._getLamps()

        try:
            lampProg = os.popen('%s on %s' % (self.lampsCmd, ' '.join(lamps)), 'r')
            states = lampProg.readline()
            lampProg.close()
        except:
            raise Exception("Failed to turn on the lamps")

        return states.strip()

    def _doOff(self, lamps):

        try:
            lampProg = os.popen('%s off %s' % (self.lampsCmd, ' '.join(lamps)), 'r')
            states = lampProg.readline()
            lampProg.close()
        except:
            raise Exception("Failed to turn on the lamps")
        
        return states.strip()

    
if __name__ == "__main__":
    l = tlamps()
    print l._getLamps()
    
