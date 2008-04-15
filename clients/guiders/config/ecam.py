# Where the camera files are saved.
imageHost = 'tycho.apo.nmsu.edu'
imageRoot = '/export/images/'           # on imageHost
imageDir = 'ecam'                       # w.r.t. imageRoot
maskFile = '/export/images/keep/masks/ecam.fits'
biasFile = '/export/images/keep/masks/ecam-bias.fits'
rawPath = '/export/images/forTron/guider'

requiredInst = 'Echelle'
requiredPort = 'NA1'
guiderType = 'inst'
imCtrName = 'IImCtr'
imScaleName = 'IImScale'

# Various attributes of the Roper camera
ccdSize = [512,512]
binning = [1, 1]

bias = 475.0
readNoise = 7.9
ccdGain = 4.6
saturation = 65535

# And of the guider
# The PyGuide dataCut: sigma above background to consider a star.
thresh = 2.5
cradius = 30.0
radMult = 1.0
retry = 10
restart = 'stop'

vetoWithFindstars = False
vetoLimit = 3.0
doFlatfield = True
doMaskfield = True
doAutoDark = False

minOffset = 0.1                         # Smallest offset we try to make.

# fitErrorScale uses the error estimate to scale the generated offsets.
# The array contains pairs of numbers: an error threshold in pixels, and a scale.
# If the error falls with a given threshold, the corresponding factor is
# applied to the offset. If the error exceeds the largest threshold, the offset
# is zeroed.
fitErrorScale = [(0.3, 0.8),
                 (0.7, 0.5),
                 (5.0, 0.3)]
