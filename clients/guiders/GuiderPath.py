__all__ = ['GuiderPath']

import os

import CPL

class GuiderPath(object):
    def __init__(self, rootDir, nameChar):
        self.rootDir = rootDir
        self.reservedPath = None, None
        self.nameChar = nameChar
        self.retries = 0
        self.lastPath = None
        
    def __str__(self):
        return "GuiderPath(rootDir=%s, reservedPath=%s, nameChar=%s" % \
               (self.rootDir, self.reservedPath, self.nameChar)
    

    def getReservedFile(self): return self.reservedPath[1]
    def getReservedDir(self): return self.reservedPath[0]
    def getReservedPath(self): return os.path.join(*self.reservedPath)

    def lockNextFilename(self, cmd):
        if self.getReservedFile():
            cmd.warn('text="overwriting reserved filename."')

        self._reserveFilename()

        return self.getReservedPath()

    def unlock(self, cmd, filename):
        if not self.getReservedFile():
            cmd.warn('text="no filename has been reserved"')
        elif self.getReservedPath() != filename and filename != None:
            cmd.warn('text=%s' % \
                     (CPL.qstr("reserved filename (%s) does not match consumed filename (%s)" % \
                               (self.getReservedPath(), filename))))

        self._updateLastImageFile()
        self.reservedPath = None, None

    def _updateLastImageFile(self):
        fname = self.getReservedFile()
        CPL.log("guiderPath", "saving %s" % (fname))
        if not fname:
            return

        f = open(os.path.join(self.baseDir, "last.image"), "w+")
        f.seek(0,0)
        f.write('%s\n' % (self.getReservedFile()))
        f.close()

        self.lastPath = self.getReservedPath()
        
    def getLastPath(self):
        """ Return the full path of the last file written """

        f = open(os.path.join(self.reservedPath[0], "last.image"), "r")
        lastFile = f.read()
        f.close()

        lastPath = os.path.join(self.reservedPath[0], lastFile)

        return lastPath
    
    def _reserveFilename(self):
        """ Return the next available filename.

        We try to not suffer collisions by putting the files in per-day directories.

        This is where we create any necessary directories. And we do that expensively,
        by checking for each file whether the right directory exists.

        We want the directories to change at local noon and be named after the
        new day's date. 
        """

        dateString = CPL.getDayDirName()
        dirName = os.path.join(self.rootDir, dateString)
        if not os.path.isdir(dirName):
            os.mkdir(dirName)
            os.chmod(dirName, 0775)

            id = 1
        else:
            # Update the last.image file
            #
            f = open(os.path.join(dirName, "last.image"), "r+")
            lastFileName = f.read()
            f.close()
            if len(lastFileName) == 0:
                id = 1
            else:
                lastID = int(lastFileName[1:5], 10)
                id = lastID + 1
            
            if id > 9999:
                raise RuntimeError("guider image number in %s is more than 9999." % (dirName))

        fileName = "%s%04d.fits" % (self.nameChar, id)
        self.reservedPath = dirName, fileName
        self.baseDir = dirName

        CPL.log("guiderPath", "reserved %s, %s" % (dirName, fileName))
        
