__all__ = ['ImageFrame']

import pyfits

import CPL

class ImageFrame(object):
    """ Maintain the transformations between:
           - CCD-centric (full-frame, unbinned pixels).
           - image-frame (subframed, binned pixels)
           - sky coordinates.

    """

    def __init__(self, ccdSize):
        """
        Args:
             ccdSize     - [x, y], in unbinned pixels
        """

        self.ccdSize = tuple(ccdSize)

    def __str__(self):
        try:
            fsize = "size=(%d,%d)" % tuple(self.frameSize)
        except:
            fsize = "size undefined"

        try:
            fbinning = "binning=(%d,%d)" % tuple(self.frameBinning)
        except:
            fbinning = "binning undefined"
            
        try:
            foffset = "offset=(%d,%d)" % tuple(self.frameOffset)
        except:
            foffset = "offset undefined"
            
        return "ImageFrame(ccdSize=(%d,%d), %s, %s, %s)" % \
               (self.ccdSize[0], self.ccdSize[1],
                fbinning, foffset, fsize)
    
    
    def setImageFromFITSFile(self, filename):
        """ Set our image subframe from the given FITS file.

        Args:
             filename   - an absolute pathname for a FITS file, which must
                          contain the followig cards:

                          NAXIS1, NAXIS2    - for the size
                          BINX, BINY        - for the binning factors
                          BEGX, BEGY        - for the offset
        """

        fits = pyfits.open(filename)
        h = fits[0].header
        fits.close()

        self.setImageFromFITSHeader(h)
    
    def setImageFromFITSHeader(self, h):
        """ Set our image subframe from the given pyfits header .

        Args:
             h   - a pyfits header, which must contain the following cards:
                          NAXIS1, NAXIS2    - for the size
                          BINX, BINY        - for the binning factors
                          BEGX, BEGY        - for the offset
        """


        try:
            binning = (h['BINX'], h['BINY'])
        except KeyError:
            binning = (3,3)

        try:
            offset = (h['BEGX'], h['BEGY'])
        except KeyError:
            offset = (0,0)
            
        size = (h['NAXIS1'], h['NAXIS2'])
        
        self.setImageFromFrame(binning, offset, size)

    def setImageFromFrame(self, binning, offset, size):
        """ Set our image subframe directly.

        Args:
           binning    - (x, y)
           offset     - (x0, y0), in binned pixels
           size       - (x, y) in binned pixels

        """

        self.frameBinning = binning
        self.frameOffset = offset
        self.frameSize = size

        self.trimSelf()
        
    def setImageFromWindow(self, binning=None, window=None):
        """ Set our image subframe.

        Args:
           binning    - (x, y)
           window     - (x0, y0, x1, y1), in binned pixels. If None, use the full frame.

        The window is trimmed to the actual CCD size.
        """

        if not binning:
            binning = [1,1]
        self.frameBinning = binning

        if window:
            self.frameSize = [window[2]-window[0]+1,
                              window[3]-window[1]+1]
            self.frameOffset = [window[0], window[1]]
        else:
            self.frameOffset = [0,0]
            self.frameSize = [self.ccdSize[0] / binning[0],
                              self.ccdSize[1] / binning[1]]                              
        self.trimSelf()

    def trimSelf(self):
        """ Adjust our size & offset to fit within the CCD frame.
        """

        CPL.log('trimSelf', 'start=%s' % (self))
        self.frameOffset = list(self.frameOffset)
        self.frameSize = list(self.frameSize)

        # Bottom/left edges
        if self.frameOffset[0] < 0:
            self.frameSize[0] -= self.frameOffset[0]
            self.frameOffset[0] = 0

        if self.frameOffset[1] < 0:
            self.frameSize[1] -= self.frameOffset[1]
            self.frameOffset[1] = 0

        # Top/right edges
        size = self.frameSize[0] * self.frameBinning[0]
        if size == 0:
            self.frameSize[0] = self.ccdSize[0] / self.frameBinning[0]
        if self.frameOffset[0] + size > self.ccdSize[0]:
            self.frameSize[0] = (self.ccdSize[0] / self.frameBinning[0]) - self.frameOffset[0]

        size = self.frameSize[1] * self.frameBinning[1]
        if size == 0:
            self.frameSize[1] = self.ccdSize[1] / self.frameBinning[1]
        if self.frameOffset[1] + size > self.ccdSize[1]:
            self.frameSize[1] = (self.ccdSize[1] / self.frameBinning[1]) - self.frameOffset[1]

        self.frameOffset = tuple(self.frameOffset)
        self.frameSize = tuple(self.frameSize)

        CPL.log('trimSelf', 'end=%s' % (self))
        
    def imgXY2ccdXY(self, imgXY):
        """ Convert an image-frame coordinate to a ccd-fram coordinate.

        Args:
           imgXY      - (x, y) in binned, frame-coordinate pixels

        Returns:
           - (ccdX, xxdY)  - unbinned, ccd-frame pixels
        """

        ccdX = (self.frameOffset[0] + imgXY[0]) * self.frameBinning[0]
        ccdY = (self.frameOffset[1] + imgXY[1]) * self.frameBinning[1]

        return (ccdX, ccdY)

    def ccdXY2imgXY(self, ccdXY, doTruncate=False):
        """ Convert an ccd-frame coordinate to a image-frame coordinate.

        Args:
           ccdXY      - (x, y) in unbinned pixels
           doTruncate - if True, force the return coordinate into the
                        image frame

        Returns:
           - (imgX, imgY)  - binned, image-frame pixels
        """

        imgX = (ccdXY[0] / self.frameBinning[0]) - self.frameOffset[0] 
        imgY = (ccdXY[1] / self.frameBinning[1]) - self.frameOffset[1] 

        if doTruncate:
            if imgX < 0:
                imgX = 0
            elif imgX >= self.frameSize[0]:
                imgX = self.frameSize[0] - 1

            if imgY < 0:
                imgY = 0
            elif imgY >= self.frameSize[1]:
                imgY = self.frameSize[1] - 1

        return (imgX, imgY)
    
    def imgFrame(self):
        """ Return the pieces of the image frame.

        Returns:
            - (x, y)   binning
            - (x0, y0)  offset in binned pixels
            - (w, h)   width in binned pixels
        """

        return self.frameBinning, self.frameOffset, self.frameSize

    def imgFrameAsCtrAndSize(self):
        """ Return the image frame (offset & size) as a window (x0,y0,x1,y1)

        Args:
          inclusive   - if true, x1 = 0 includes pixel 0

        Returns:
          [ctrX, ctrY]    - frame center, in _floating point_ binned pixels
          [w, h]          - frame size, in _floating point_ binned pixels

        """

        x = self.frameOffset[0] + self.frameSize[0]/2.0
        y = self.frameOffset[1] + self.frameSize[1]/2.0

        return (x, y), \
               (float(self.frameSize[0]), \
                float(self.frameSize[1]))

    def imgFrameAsCornerAndSize(self):
        """ Return the image frame (offset & size) as a window (x0,y0,x1,y1)

        Args:
          inclusive   - if true, x1 = 0 includes pixel 0

        Returns:
          [offsetx, offsety] - frame center, in binned pixels
          [w, h]             - frame size, in binned pixels

        """

        return (self.frameOffset[0], self.frameOffset[0]),\
               (self.frameSize[0], self.frameSize[1])

    def imgFrameAsWindow(self, inclusive=True):
        """ Return the image frame (offset & size) as a window (x0,y0,x1,y1)

        Args:
          inclusive   - if true, x1 = 0 includes pixel 0

        Returns:
          x0, y0, x1, y1  - frame in binned pixels. x1,y1 are inclusive.
        """

        x0 = self.frameOffset[0]
        y0 = self.frameOffset[1]

        if inclusive:
            skooch = 1
        else:
            skooch = 0
            
        return x0, y0, \
               x0 + self.frameSize[0] - skooch, \
               y0 + self.frameSize[1] - skooch

               
               
    
