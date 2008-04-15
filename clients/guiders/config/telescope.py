# How far we can move before the offset needs to be computed, in arcseconds.
# This is underspecified: what we care about is how far an individual axis
# can move before it jerks.
maxUncomputedOffset = 10.0

# How far any guide offset can go. Note that centering offsets are guide offsets.
maxGuideOffset = 220.0

# How far it is worth trying to move, in arcseconds
minOffset = 0.1

# How long we need to wait for an uncomputed offset to complete.
offsetSettlingTime = 0.75



