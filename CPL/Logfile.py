from __future__ import division
from builtins import range
from past.utils import old_div
from builtins import object
__all__ = ['Logfile']

import os
import os.path

from time import time, gmtime, strftime, sleep
from math import modf

class Logfile(object):
    """ A simple class offering timestamped logs to timestamped files. We maintain a logging threshold,
    against whch logging requests are compared.
    """
    
    def __init__(self, logDir, level=1, EOL='\n', doEncode=False):
        """
        Args:
           logDir       - a directory name inside which we create our logfiles.
           level     - a threshold. Logging requests with a level at or below this are logged.
           EOL       - a string to terminate log lines with. Set to '' to not add newlines.
           doEncode  - If True, use %r rather than %s to encode the log text.
        """
        
        self.logDir = logDir
        self.level = level
        self.EOL = EOL
        self.doEncode = doEncode
        
        self.rolloverTime = 0
        self.rolloverChunk = 24*3600
        self.rolloverOffset = 0

        if not os.path.isdir(self.logDir):
            os.makedirs(self.logDir, 0o755)
        self.log('logger', 'log started', level=0)
            
    def setLevel(self, level):
        lastLevel = self.level
        self.level = level
        return lastLevel

    def getLevel(self):
        return self.level
    
    def newLogfile(self):
        """ Close the current logfile and open a new one.

        We use the current time to name the file. 
        """

        self.rolloverTime = 0
        try:
            self.logfile.close()
        except:
            pass
        
    def rollover(self, t):
        if t <= self.rolloverTime:
            return
        
        self.rolloverTime = t - t%self.rolloverChunk + self.rolloverChunk + self.rolloverOffset
        logfileName = "%s.log" % (strftime("%Y-%m-%dT%H:%M:%S", gmtime(t)))
        self.logfile = open(os.path.join(self.logDir, logfileName), "w", 1)
        currentName = os.path.join(self.logDir, "current.log")
        try:
            os.unlink(currentName)
        except:
            pass
        os.symlink(logfileName, currentName)

    def getTS(self, t=None, format="%Y-%m-%d %H:%M:%S", zone="Z"):
        """ Return a proper ISO timestamp for t, or now if t==None. """

        if t == None:
            t = time()

        if zone == None:
            zone = ''

        return strftime(format, gmtime(t)) \
               + ".%04d%s" % (10000 * modf(t)[0], zone)
    
    def log(self, txt, note="", level=1):
        """ Append txt to our log if the given level is <= self.level.

        Args:
            txt - the bulk of the text to log.
        """

        if level > self.level:
            return
        
        now = time()
        self.rollover(now)
        ts = self.getTS(t=now)

        if self.doEncode:
            self.logfile.write("%s %s %r%s" % (ts, note, txt, self.EOL))
        else:
            self.logfile.write("%s %s %s%s" % (ts, note, txt, self.EOL))
        
def test():
    l = Log('/tmp/tlogs')

    for i in range(20):
        l.log("logging %d and pausing 1s" % (i))
        sleep(1)

    n = 10000
    start = time()
    for i in range(n):
        l.log("logging %d" % (i))
    end = time()
    l.log("%d lines in %0.3fs, or %d lines/s" % \
          (n, (end - start), old_div(n,(end -  start))))

if __name__ == "__main__":
    test()
    
        
