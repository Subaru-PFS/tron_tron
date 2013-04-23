Installing the MHS and actors
=============================

..todo:: This documents a test, or sample instalation, but **NOT**
what a real developer would use, nor a propoer operational
installation. Split things up, or refactor installation...

The MHS system is maintained as a collection of git repositories in
the gitolite collection at pfs.ipmu.jp. The central parts are:

 - the 'tron' hub repo.
 - an 'actorcore' infrastructure library repo.
 - several repositories for individual "actors", each of which
   encapsulates a subsystem or provides some control logic.
 - an 'actorkeys' repo, which contains the published keyword
   dictionaries for all the individual actors.

All of these require a recent python. 2.6 is probably OK, 2.7
certainly is. The actors also require twisted, numpy, and
pyfits. These are common enough packages that we can probably expect
them to be installed on the machines. 

..todo:: Find or write intro document on eups: why use it and how?
Check recent ``modules`` at sourceforge.

The system uses a package management system named 'eups'. In the
introductory installation below, none of the interesting features of
eups are used, but it becomes very useful once you need to maintain
multiple versions of packages, and packages with dependencies.

Note that the http://modules.sourceforge.net/ system is similar. We
have not recently evaluated whether it would be sufficient.

Fetching the pieces
-------------------

The simplest way to start is to run the simple bootstrapping script
available at *XXX* (for now, in the
gitolite@pfs.ipmu.jp:ics_mhs_config repo, in bin/bootstrap_mhs). This
installs development versions of the core MHS products in `~mhs`, and
arranges for logs and image files to also be saved in that
directory. Before running the script, you can modify the ICS_ROOT
variable if you want to use a different root directory.

If the `eups` product manager is not running, the script starts by
installing the latest version from::

    git clone -b 1.2.33 git@github.com:RobertLuptonTheGood/eups 

It then installs all the current MHS hub and actor
repositories. Currently these are::

    git clone gitolite@pfs.ipmu.jp:ics_mhs_config
    git clone gitolite@pfs.ipmu.jp:ics_mhs_actorcore
    git clone gitolite@pfs.ipmu.jp:ics_mhs_actorkeys
    git clone gitolite@pfs.ipmu.jp:ics_mhs_tron
    git clone gitolite@pfs.ipmu.jp:ics_mhs_mcsActor
    git clone gitolite@pfs.ipmu.jp:ics_mhs_mpsActor
    git clone gitolite@pfs.ipmu.jp:ics_mhs_pficsActor
    git clone gitolite@pfs.ipmu.jp:ics_mhs_root

There will be a `source` command shown at the bottom of all that
output. If you are not already using `eups`, you will want to add that
to your login scripts, and you will need to run it now. Something
like::

    source $ICS_ROOT/products/eups/bin/setups.{sh,csh,zsh}

Running the ICS MHS hub
-----------------------

The `ics_mhs_root` product is (currently) just a convenience, to allow
setting up all the MHS parts at once. If `eups` is correctly
configured::

  setup ics_mhs_root 

will do that, and return silently. The tron hub itself is a
long-running process. Start it with::

  tron start

which should have no output.

Running the ICS MHS actors
--------------------------

There are currently three configured actors, one of which should be a
pretty good template. The three implement the bones of a `guide loop`
controlling the fiber actuators. MCS (`mcsActor`) stands in for the
Metrology Camera, MPS stands in for the positioner system, and PFICS
stands in for the fiber control system. I realize that the PFICS and
MPS actors are not currently independant systems, but it would have
been a perfectly decent architecture.

Before starting the actors, it might be useful to launch a (very) simple
tk-based console. Actually, for reasons I'll get to later, start two::

    hubclient &
    hubclient &

OK. The three actors are started individually. All current actors can
be started directly from python, or from the `stageManager` wrapper
script, like::

    stageManager mcsActor start
    stageManager mpsActor start
    stageManager pficsActor start

When each actor is started, it connects to a single published hub
port, and tells the hub to launch a connection back to itself. The
slightly cryptic output from all this should appear in the two
hubclients.

_Aside_: the hub and actors are currently configured to only connect
to and listen for `localhost` connections. In general they can be
anywhere, but we should discuss security before opening anything up.

Operating the ICS actors
------------------------

The connected actors can now be commanded from, say, a hubclient. At
the bottom of the hubclient windows is a text field where you can
enter direct commands. The syntax is a) the name of an actor and b)
the command. For instance, send `mcs help` or `mcs status`, or `hub
status`. Note in `mcs status` the `expose` and `centroid` commands,
and take a couple of "exposures"::

    mcs expose bias
    mcs expose object expTime=2.0

In the `hubclient` you are sending the commands from, you should see
responses, including a filename keyword. There should, in fact, be
real files on disk. 

The other `hubclient` does not show those keywords. The current
configuration arranges for each connection to only see the responses
to the commands it sends. The reason for this choice will be more
obvious when you send the `centroid` command, which returns an encoded
array of 4000 (x,y) centroids::

    mcs centroid expTime=0.5

Finally, you can request a test of a PFICS "loop"::

    pfics help
    pfics help cmds=testloop
    pfics testloop cnt=5 expTime=0.0

Development
-----------

This bootstrap installation is just that: just enough to get a running
system going. I have not linked in the protocol documentation yet, and
many SDSS systems (authentication, alarms, image directory and
filename sequence encapsulation, standard FITS header generation,
etc.) have either been stubbed out or turned off.

One thing I will point out now. The `mcsActor` is probably a decent
template to start from. I will defer getting into the details of
proper git and eups etiquette; in the meanwhile you can modify the
code in $ICS_MHS_MCSACTOR_DIR. In particular, you can modify the
python/mcsActor/Commands/McsCmd.py file while the actor is running and
dynamically reload it with `mcs reload`. If you do not add any
non-restartable persistent state to the McsCmd.py file, you can edit
and test at will, including modifying the command vocabulary.

Chapter II
----------

Yeah, yeah, yeah....





