__all__ = ['GCamera']

""" GCamera.py -- base guide camera controllers.

    A "guide camera" is a _simple_ device. It can:
     - expose for S seconds
    
    It can optionally:
     - take S seconds darks
     - window and bin both exposures and darks.

    The images are saved to disk, using the date as a filename.
"""

import os.path
import time

class GCamera(object):
    def __init__(self, name, path, **argv):

        self.name = name
        
        # Basic sanity checks _now_
        #
        if not os.path.isdir(path):
            raise RuntimeError("path given to %s is not a directory: %s" % (name, path))

        self.path = path
        self.exposeCmd = None
        
    def _getFilename(self):
        """ Return the next available filename.

        We try not to suffer collisions by naming the files with timestamps and
        putting them in per-day directories.

        This is where we create any necessary directories. And we do that expensively,
        by checking for each file whether the right directory exists.

        We want the directories to change at local noon and be named after the
        new day's date. 
        """

        now = time.time()
        localNow = now - time.altzone
        localNowMinus12H = local - (12 * 3600)
        
        dateString = time.strftime("%Y-%m-%d", time.gmtime(localNowMinus12H))
        timeString = time.strftime("%H%M%S", time.gmtime(now))

        dirName = os.path.join(self.path, dateString)
        if not os.path.isdir(dirName):
            os.mkdir(dirName)
            os.chmod(dirName, 0777)
        return os.path.join(dirName, "%s.fits" % (timeString))

    def cidForCmd(self, cmd):
        return "%s.%s" % (cmd.fullname, self.name)
    
