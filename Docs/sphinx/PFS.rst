Possible Architecture for PFS
=============================

PFS includes at least the following independant devices:

 - four spectrographs.
 - a fiber actuator controller
 - calibration lamp controller
 - a metrology camera
 - acquisition/guide camera
 - a connection to the observatory Gen2 system (telescope, etc)

I suspect that most of these can be treated as fairly simple
independant actors, with a few interesting issues.

Simple Devices
--------------

The calibration lamp controller and the two small cameras could be
wrapped with quite small programs. We have found that having camera
programs which just take exposures, save them to disk, and return some
filename/URL key works extremely well: it is a clean division of
functionality which improves reliability, testing, and
provenance. These days the overhead is miniscule.

The Spectrographs
-----------------

The interesting problem is how to write files and in particular the
headers. We have found it useful to exploit the fact that all external
actor state is always available: the FITS headers can safely be
constructed while the data are still in memory, so that no further
dangerous file operations are required. The headers can be built using
the latest (best) information, but without the need for any risky
external status queries during integration/readout/IO.

The Subaru Gen2 Interface
-------------------------

I have only glanced at the requirements here, but I would be strongly
tempted to write a translator which generates keywords describing the
telescope status and environment. Other actors could then use those
native keywords to, say, populate FITS heeaders. Obviously commands
from Gen2 would also need to be run. I do not know how much work this
is, but I am pretty confident that python would be a good tool.

The Fiber Actuator Controller
-----------------------------

This is the one I have the least sense about. I'm pretty sure that
having the camera separate would not be a performance bottleneck. That
said, I suspect that the camera and fiber controller actors should run
on the same host, to avoid NFS inefficiencies.

Other connections
-----------------

I assume that some operational database will be required, to provide
fiber layouts, to track field, exposure and S/N performance, to drive
field selection, etc. One design choice will be how to provide all
that.

One side effect of having all actor traffic broadcast is that it is
trivial to add an archiving logger which keeps a complete record of
all actors' state.

The guider will need to know about guide probe geometry and guide star
properties, take camera exposures, and command offsets. One natural
structure is a standalone actor which runs an expose-measure-offset
loop, handing off the exposures, offsets, and probe management to
other actors.
