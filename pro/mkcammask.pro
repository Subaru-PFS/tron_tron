;+
; NAME:
;   mkcammask
;
; PURPOSE:
;      Create a flatfield + mask file.
;
; CALLING SEQUENCE:
;      mkcammask, innames, outname, thresh, reqsize [, /dopad]
;
; INPUTS:
;   innnames   - a list of filenames, which must be full-frame,
;                unbinned flatfields images. These will be medianned
;                together.
;   outname    - the filename which will be written to.
;   thresh     - a threshold [0..1] below which the output pixel will
;                be set to 0.
;
; OPTIONAL KEYWORDS:
;   /dopad     - if set, pad the input images by one pixel. This is to
;                fix a buggy camera controller.
;
; COMMENTS:
;   The output is the median of the input images w.r.t. the median
;   pixel value, with low-valued pixels set to 0. Areas with low
;   pixels are slighty dilated to smooth around marginal areas.
;
;-
pro mkcammask,innames,outname,thresh,reqsize,pad=pad
 
                                ; Median the input masks.
    n = n_elements(innames)
    for i=0,n-1 do begin
        f = mrdfits(innames[i], /unsigned)
        s = size(f, /dimensions)
        w = s[0]
        h = s[1]
                                ; The GImg controller undersizes full frame images. Grrr.
        if keyword_set(pad) then begin
            s[0] = s[0] + pad
            s[1] = s[1] + pad
        end
        
        if s ne reqsize then $
          message, string('input images must be ', reqsize, ' not ', s, ' : ', innames[i], $
                          format='(a,2f,a,2f,a,a)')

        if i eq 0 then begin
            files = fltarr([n,s])
        endif

        if keyword_set(pad) then begin
            files[i,w,*] = median(f)
            files[i,*,h] = median(f)
            files[i,0:w-pad,0:h-pad] = f
        end else begin
            files[i,*,*] = f
        end

        print,"min=", min(files[i])
    endfor

    med_image = median(files, dimension=1)
    med_pixel = median(med_image)

    flat_image = med_image / med_pixel

                                ; OK, heuristics here. Start the mask
                                ; with some fairly low level, then
                                ; grow it a bit to remove hair.
    mask = flat_image lt thresh

    r3 = replicate(1,3,3)
    r5 = replicate(1,5,5)
    mask = dilate(erode(mask, r3), r5)

                                ; Save an inverse flat, with 0 for masked
                                ; pixels. This lets us safely multiply
                                ; the image file by the mask/flat file.
    image = (1.0 / flat_image) * (1 - mask)

    sxaddpar, h, 'THRESH', tresh, 'Pixels below this were set to 0'
    for i=0,n_elements(innames)-1 do $
      sxaddpar, h, string('INFILE',i,format('a6,i02')), innames[i], 'Input file name.')
    sxaddpar, h, 'OUTFILE', outname, 'Original output file name'
    sxaddpar, h, 'MASKDATE', systime(), 'Mask file creation date, local time'

    mwrfits, image, outname, h, /create
end
