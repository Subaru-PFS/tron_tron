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
; frebin_mask, 'na2.fits', 'na2-3x3.fits', [80,90], [40,50], [3x3]
;
; MODIFICATION HISTORY:
;
;-

pro fsubframe,infileName,outfileName,offset,size,binning

                                ; Read in the unbinned mask file and figure its size
  inData = mrdfits(infileName, /unsigned)
  fullSize = (size(inData))[1:2]

                                ; 
                                ; Find out if we need to trim the input array: rebin 
                                ; only scales by integer factors.
  binnedSize = fullSize / binning
  trimSize = binnedSize * binning

  if not array_equal(trimSize, fullSize) then begin
      inData = inData[0:trimSize[0]-1, 0:trimSize[1]-1]
  end
                                ; Now scale the possibly trimmed data.
                                ; First, force the data to be a true 0 or 1 mask.
                                ; Convert that to a floating point array
                                ; so that we can decide how much masking
                                ; in the input array yields a mask pixel
  inData = float(inData ne 0)
  binnedData = rebin(inData, binnedSize)
  
                                ; If half the input pixels were masked, generate
                                ; an masked output pixel.
                                ; For consistency, save to an "unsigned int" fits file.
                                ; It may be safe, or even desirable, to save a byte array,
                                ; but numarray can be quirky.

  binnedData = uint(binnedData gt 0.5)

  mwrfits, binnedData, outfileName, iscale=[1.0, 32768.0], /create

  return
end
