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

All physical communication does go through a central hub, but logical
command flow is directly between actors. For a sketch of one PFS
architecture, see `PFS Architecture <PFS_architecture.pdf>`.

Simple Devices
--------------

The calibration lamp controller as well as the metrology, acquisition,
and guide cameras can all be wrapped with quite small programs. We
have found that having camera programs which just take exposures, save
them to disk, and return some filename/URL key works extremely well:
it is a clean division of functionality which improves reliability,
testing, and provenance. These days the overhead is miniscule.

That said, it can be reasonable for a camera controller to also
generate keywords enumerating peak positions.

The Spectrographs
-----------------

The interesting problem is how to write files and in particular the
headers. All external actor state is always available: the FITS
headers can be constructed by the spectrograph controllere while the
data are still in memory, so that no further file operations are
required. 

The Subaru Gen2 Interface
-------------------------

The Subaru Gen2 system provides all the telescope and environmental
information required for instrument FITS headers, and passes commands
down to the instrument. From the observatory's point of view, the
instrument appears as a single program. The natural aarchitecture is
to implement a single translator which generates keywords describing the
telescope status and environment and which converts Gen2 commands to
ICS actor commands.

The Fiber Actuator Controller
-----------------------------

This is the one I have the least sense about. I'm pretty sure that
having the camera separate would not be a performance bottleneck. The
control loop between the camera and the PFI can probably be abstracted
out into its own software coomander. That said, it would be smart to
run the camera, fiber actuator, and fiber control loop actors on the
same host, to avoid NFS and other latencies.

Other connections
-----------------

 - One nice side effect of having all actor traffic broadcast is that
   it is trivial to add an archiving logger which keeps a complete
   record of all commands and replies, thus also all actor state.

 - I assume that some operational database will be required to provide
   fiber layouts, to track field, exposure and S/N performance, to
   drive field selection, etc. One design choice will be how to
   provide all that.

 - The guider will need to know about guide probe geometry and guide
   star properties, take camera exposures, and command offsets. One
   natural structure is a standalone actor which runs an
   expose-measure-offset loop, handing off the exposures, offsets, and
   probe management to other actors.

 - A PFI control loop would be similar to a guider.

 - I am not sure that it is the right tool, but we do have a fairly
   adaptable python/tk/X11 GUI program which can be used to control
   hub-connected systems, either during development or operations.
