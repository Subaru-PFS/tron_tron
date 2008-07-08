# Where the camera files are saved.
imageDir = 'tcam'
imageRoot = '/export/images/'
imageHost = 'newton.apo.nmsu.edu'
maskFile = '/export/images/keep/masks/tcam/tcam.fits'
#biasFile = '/export/images/keep/masks/tcam/tcam-bias.fits'
biasFile = None

requiredInst = 'TSPEC'
requiredPort = 'NA2'
guiderType = 'inst'
imCtrName = 'IImCtr'
imScaleName = 'IImScale'

# Various attributes of the TCAM slitviewer camera
ccdSize = [1024,1024]
binning = [2, 2]

bias = 0.0
readNoise = 10.0 # unknown
ccdGain = 4.5
saturation = 60000
doFlatfield = True
doMaskfield = True
doAutoDark = False

# And of the guider

# The PyGuide dataCut: sigma above background to consider a star.
thresh = 2.5
cradius = 35.0
radMult = 1.2
retry = 8
restart = 'stop'

vetoWithFindstars = False
vetoLimit = 3.0

minOffset = 0.1                         # Smallest offset we try to make, in arcseconds.

# fitErrorScale uses the error estimate to scale the generated offsets.
# The array contains pairs of numbers: an error threshhold, and a scale.
# If the error falls with a given threshold, the corresponding factor is
# applied to the offset. If the error exceeds the largest threshold, the offset
# is zeroed.
fitErrorScale = [(0.3, 0.8),
                 (0.7, 0.5),
                 (5.0, 0.3)]

