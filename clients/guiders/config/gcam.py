# Where the camera files are saved.
imageDir = 'gcam'
imageRoot = '/export/images/'
imageHost = 'newton.apo.nmsu.edu'
maskFile = '/export/images/keep/masks/gcam.fits'
biasFile = None # '/export/images/keep/masks/gcam-bias.fits'

requiredInst = None
requiredPort = 'NA2'
guiderType = 'gimage'
imCtrName = 'GImCtr'
imScaleName = 'GImScale'

# Various attributes of the Alta camera
cameraHostname = 'na2alta.apo.nmsu.edu'
ccdSize = [1024,1024]
binning = [3, 3]

bias = 1800.0                           # Very Suspect. See ecam.py
readNoise = 21.3
ccdGain = 1.6
saturation = 65535

# And of the guider

# The PyGuide dataCut: sigma above background to consider a star.
thresh = 2.5
cradius = 20.0
radMult = 1.7
retry = 5
restart = 'stop'

vetoWithFindstars = False
vetoLimit = 3.0
doFlatfield = True
doMaskfield = True
doAutoDark = False

minOffset = 0.1                         # Smallest offset we try to make, in arcseconds.

# fitErrorScale uses the error estimate to scale the generated offsets.
# The array contains pairs of numbers: an error threshhold, and a scale.
# If the error falls with a given threshold, the corresponding factor is
# applied to the offset. If the error exceeds the largest threshold, the offset
# is zeroed.
fitErrorScale = [(0.3, 0.8),
                 (0.7, 0.5),
                 (5.0, 0.3)]

