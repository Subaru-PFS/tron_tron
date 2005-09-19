pro mkdcammask,innames,outname,thresh

                                ; Median the input masks.
    n = n_elements(innames)
    for i=0,n-1 do begin
        f = mrdfits(innames[i], /unsigned)
        if i eq 0 then begin
            s = size(f, /dimensions)
            w = s[0]
            h = s[1]
            files = fltarr([n,s])
        endif
        ;files[i,0:w-1,0:h-1] = f
        files[i,*,*] = f
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
    mwrfits, image, outname, /create
end
