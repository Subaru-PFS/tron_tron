""" Exposure path and file handling.

    We assign a root directory to each program, under which the users can play as they wish.
    The program can get a sequence of filenames, or a sequence of files. In either case, all
    possible sanity checks are performed before a new file or filename is returned.

"""

import glob
import os
import os.path

import sys
sys.path.insert(0, "..")

import CPL

class ExpPath(object):

    month2quarters = { '01' : 'Q1',
                       '02' : 'Q1',
                       '03' : 'Q1',
                       '04' : 'Q2',
                       '05' : 'Q2',
                       '06' : 'Q2',
                       '07' : 'Q3',
                       '08' : 'Q3',
                       '09' : 'Q3',
                       '10' : 'Q4',
                       '11' : 'Q4',
                       '12' : 'Q4'
                       }
                       
    def __init__(self, cmdrID, inst,
                 userDir="", name="test.", number=1, places=4,
                 needSize=10000000, suffix=".fits", rootDir="/export/images"):

        """ Define an image filename sequence:

        Args:
          cmdrID     - the name of the observing program
          userDir    - the name is the directory under rootDir
          name       - the base name of the files to be created in rootDir/userDir
          number     - the first sequence number. Can be 'next' as well as a positive integer.
          places     - how many places to allocate to the sequence number.

        Notes:
          Checks whether the program name can be used to specify a legitimate directory and
          whether the userDir specifies a useable dirctory. The final directory is created, 0777.

        Raises:
          Error.
          
        """

        # Make sure the program path does not escape from our root directory.
        #
        self.cmdrID = cmdrID.strip()
        program, user = self.cmdrID.split('.')
        self.program = program.strip()
        self.inst = inst

        if self.inst == 'dis':
            self._checkFileAccess = self._checkDISFileAccess
        else:
            self._checkFileAccess = self._checkSimpleFileAccess
        
        self.rootDir = rootDir.strip()
        self._adjustProgramDir()
        
        d = os.path.join(self.rootDir, self.programDir)
        if self._isSneakyDir(d):
            raise CPL.Error("I don't trust the program name %s" % (CPL.qstr(program, tquote="'")))

        #userDir, name = self.normalizeDir(userDir, name)
        #CPL.log("ExpPath", "dir=%s, name=%s" % (userDir, name))
        
        self._checkDir(userDir)
        self._checkName(name)
        self._checkNumber(number)
        self._checkPlaces(places)
        
        self.needSize = needSize
        self.suffix = suffix

    def normalizeDir(self, userDir, name):
        """ Move any directories specified in name to userDir. """

        return os.path.split(os.path.join(userDir, name))
    
    def _checkDir(self, userDir):
        """ Check and possibly create and configure the final directory.

        Raise:
           Error
        """

        while len(userDir) > 0 and userDir[0] == '/':
            userDir = userDir[1:]
        userDir = userDir.strip()
        
        # Make sure the fully fleshed out userpath does not escape from our root directory.
        #
        d = os.path.join(self.rootDir, self.programDir, userDir)
        if self._isSneakyDir(d):
            raise CPL.Error("I don't trust the path %s" % (d))
        self.userDir = userDir
        fullDir = d
        
        # Make sure we can own or create the user directory.
        #
        if not os.path.exists(fullDir):
            try:
                os.makedirs(fullDir, 0777)
            except Exception, e:
                raise CPL.Error("could not create directory %s: %s" % (fullDir, e))
        try:
            os.chmod(fullDir, 0777)
        except Exception, e:
            raise CPL.Error("could not open up directory %s: %s" % (fullDir, e))

        
    def _checkName(self, name):
        """ Check the proposed new file basename.

        Leaves the existing name unchanged if the new name is not accepted.
        If the name specifies a directory, take that as new userDir.
        
        CHANGE: always override the userDir. Any directories must be specified in the name.
        
        Raise:
           Error
        """

        # if '/' in name:
        #     raise Error("please do not put directories in the file name")

        name = name.strip()
        userDir, name = self.normalizeDir('', name)
        if True or userDir != '':
            self._checkDir(userDir)
        CPL.log("ExpPath", "dir=%s, name=%s" % (userDir, name))
        
        # Make sure the fully fleshed out userpath does not escape from our root directory.
        #
        d = os.path.join(self.rootDir, self.programDir, self.userDir, name)
        if self._isSneakyDir(d):
            raise CPL.Error("I don't trust the path %s" % (d))

        self.name = name
        
    def _checkNumber(self, number):
        """ Check the proposed new sequence number.

        Leaves the existing number unchanged if the new number is not accepted.

        Raise:
           Error
        """

        if number == 'next':
            self.number = number
            return
        
        # Make sure the number & places args are integers
        #
        try:
            number = int(number)
        except Exception, e:
            raise CPL.Error("sequence number is not really a number: %s" % (number))
        
        self.number = number
        
    def _checkPlaces(self, places):
        """ Check the proposed new number of places for the sequence number

        Leaves the existing number unchanged if the new number is not accepted.

        Raise:
           Error
        """

        # Make sure the places args is an integer
        #
        try:
            places = int(places)
        except Exception, e:
            raise CPL.Error("sequence number places is not really a number: %s" % (places))
        
        self.places = places
        
    def _isSneakyDir(self, d):
        """ Return True if d might be more than just a simple directory.  """

        # Strip trailing '/', then let os.path rewrite the path (rewiting .., etc)
        if len(d) > 0 and d[-1] == '/':
            d = d[:-1]
        tDirChk = os.path.normpath(d)
        return d != tDirChk
        
        
    def setDir(self, newDir):
        self._checkDir(newDir)
        
    def setName(self, newName):
        self._checkName(newName)
        
    def setNumber(self, newNumber):
        self._checkNumber(newNumber)
        
    def setPlaces(self, newPlaces):
        self._checkPlaces(newPlaces)

    def _getNextNumber(self):
        """ Given a presumably safe internal configuration, find the next available sequence number.

        Basically, sort the list of files that match all but the .suffix pattern, grab the trailing
        integer from the last match, and add one.

        glob just does not work -- switch to filtering with regexps.
        """

        pattern = os.path.join(self.rootDir, self.programDir, self.userDir,
                               "%s%s?%s" % (self.name, "[0-9]" * self.places, self.suffix))
        files = glob.glob(pattern)

        CPL.log("getNextNumber", "pattern=%s, %d files: %s" % (pattern, len(files), files))
        if len(files) == 0:
            return 1

        # Find the last lexicographically sorted file name
        files.sort()
        lastFile = files[-1]

        # Extract the last sequence number. Increment it. Return it.
        fname = os.path.basename(lastFile)

        CPL.log("getNextNumber", "fname: %s" % (fname))

        # If the name part does not match, something is horribly wrong. But I think it
        # is safe to return some number.
        #
        if fname.find(self.name) != 0:
            return 999

        fnum = fname[len(self.name):]
        CPL.log("getNextNumber", "fnum: %s" % (fnum))
        fnum = fnum[:self.places]
        CPL.log("getNextNumber", "fnum: %s" % (fnum))

        try:
            fnum = int(fnum)
        except Exception, e:
            # Hell if I know what to do.
            return 999

        return fnum+1
        
        
    def _getNumber(self):
        """ Return the next sequence number. Find the next free file if necessary. """
        
        if self.number == 'next':
            n = self._getNextNumber()
        else:
            n = self.number

        return "%0*d" % (self.places, n)
    
    def _incrNumber(self):
        """ Increment the sequence number. """
        
        if self.number != 'next':
            self.number += 1

    def _adjustProgramDir(self):
        """ Make .programDir reflect the current date. 

        This is where we create any necessary directories. And we do that expensively,
        by checking for each file whether the right directory exists.

        We want the directories to change at local noon and be named after the
        new day's date. 
        """

        now = time.time()
        localNow = now - time.timezone
        localNowPlus12H = localNow + (12 * 3600)

        dateString = time.strftime("UT%y%m%d", time.gmtime(localNowPlus12H))
        quarterString = self.month2quarters(dateString[4:5])
        
        dirName = os.path.join(self.rootDir, quarterString + self.program,
                               dateString)
        if not os.path.isdir(dirName):
            os.mkdir(dirName)
            os.chmod(dirName, 0777)

        self.programDir = dirName
        
    def _fullName(self):
        return "%s%s%s" % (self.name, self._getNumber(), self.suffix)

    def _fullPath(self):
        return os.path.join(self.rootDir, self.programDir, self.userDir, self._fullName())
        
    def _allParts(self, keepPath):
        if not keepPath:
            self._adjustProgramDir()
        return self.rootDir, self.programDir, self.userDir, self._fullName()

    def _checkSimpleFileAccess(self, parts):
        """ Confirm that the parts describe a useable filename.
        """
        
        fullPath = os.path.join(*parts)

        if os.path.exists(fullPath):
            raise CPL.Error("file already exists: %s" % (fullPath))

        # Double-check directory permissions
        #
        dir = os.path.dirname(fullPath)
        if not os.access(dir, os.W_OK):
            raise CPL.Error("could not write into %s/" % (dir))


    def _checkDISFileAccess(self, parts):
        """ Confirm that the parts describe a useable pair of DIS filenames.
        """

        for color in 'r', 'b':
            colorParts = list(parts)

            colorFile = colorParts[3]
            colorFile = colorFile[:-len(self.suffix)] + "%s.fits" % (color,)
            colorParts[3] = colorFile

            self._checkSimpleFileAccess(tuple(colorParts))
            
    def getFilenameInParts(self, keepPath=False):
        """ Returns the next filename in the sequence.

        Args:
            keepPath    - if True, do not adjust the path for date/quarter rollovers.
            
        Returns:
          - The system root directory
          - The program directory. This will include:
              - the quarter name,
              - the program name,
              - the date
          - The user directory
          - The new filename
          
        Raises:
          Error on access errors.

        """

        parts = self._allParts(keepPath)
        CPL.log("getFilename", "parts=%s" % (parts,))

        self._checkFileAccess(parts)
        self._incrNumber()

        # CPL.log("getFilename", "parts=%s" % (parts))
        return parts

    def getFilename(self):
        """ Returns the next filename in the sequence.

        Returns:
          The new filename.
          
        Raises:
          Error on access errors.

        """

        return os.path.join(*self.getFilenameInParts())
        
    def getFile(self):
        """ Returns the next file in the sequence. """

        name = self.nextFilename()
        try:
            f = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0666)
        except Exception, e:
            raise CPL.Error("could not create file %s" % (name))

        return f

    def getKey(self):
        """ Return the key that describes us. """

        return "%sNextPath=%s,%s,%s,%s,%s" % (self.inst.lower(),
                                              CPL.qstr(self.cmdrID),
                                              CPL.qstr(self.userDir),
                                              CPL.qstr(self.name),
                                              CPL.qstr(self._getNumber()),
                                              CPL.qstr(self.suffix))
    
if __name__ == "__main__":
    p = ExpPath("PU01/..")
    
        
