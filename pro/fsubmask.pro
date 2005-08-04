;+
; NAME: fsubframe
;
; PURPOSE: Read an unbinned, fullframe file and write a subframed & binned file.
;
;
; CALLING SEQUENCE:
;
; INPUTS:
;    infileName        - the name of an existing fits file, assumed
;                        to be a mask file, where 0-valued pixels indicate
;                        the mask.
;    outfileName       - the name of a fits file we will create, and overwrite 
;                        if necessary. 
;    offset            - the _binned_ pixel offset of the desired subframe
;    size              - the _binned_ pixel size of the desired subframe.
;    binning           - the desired binning factor.
;
; NOTES:
;    A binned pixel is considered masked if at least half of its unbinned pixels were 
;    masked. This may not be quite right. E.g. a four-pixel corner in a 3x3 bin
;    would not survive.    
;    If the binning factor would yield fractional pixels, trim the input mask to
;    an integer factor of the binning factor.
;
; EXAMPLE:
;
; fsubframe, 'na2.fits', 'na2-3x3.fits', [80,90], [40,50], [3x3]
;
; MODIFICATION HISTORY:
;
;-

pro fsubmask,infileName,outfileName,offset,size,binning

                                ; Read in the unbinned mask file and figure its size
  inData = mrdfits(infileName, /unsigned)

                                ; Cut out a properly sized piece of
                                ; the unbinned input. The rebin
                                ; function requires the array shape to be an
                                ; integral factor of the binning factor.
  unbinnedOffset = offset * binning
  unbinnedSize = size * binning
  x0 = unbinnedOffset[0]
  y0 = unbinnedOffset[1]
  x1 = x0 + unbinnedSize[0] - 1
  y1 = y0 + unbinnedSize[1] - 1

  inData = inData[x0:x1, y0:y1]
  
                                ; Rebin the input. Note that the input
                                ; to rebin must be in integral binned
                                ; pixels.
  binnedData = rebin(inData, size)

  mask = binnedData

  mwrfits, mask, outfileName, /create

  return
end
