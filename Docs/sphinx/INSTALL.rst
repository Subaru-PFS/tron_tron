Installing the MHS and actors
=============================

..todo:: This documents a complete installation, starting from
nothing, for developing a single MHS actor and running it within the
production server-and-client environment.

The MHS system is maintained as a collection of git repositories in
the gitolite collection at pfs.ipmu.jp. The central parts are:

 - the `tron_tron` repository for the `tron` server itself.
 - the `tron_actorcore` infrastructure library repo, which implements
   the connection logic for tron clients.
 - several repositories for individual "actors", each of which
   encapsulates a subsystem or provides some control logic.
 - an 'actorkeys' repo, which contains the published keyword
   dictionaries for all the individual actors.

All of these require a recent python. 2.6 is probably OK, 2.7
certainly is. The actors also require twisted, numpy, and pyfits
(currently named 'astropy.io.fits'). We _strongly_ recommend
installing a current version of the Anaconda distribution, found at
https://store.continuum.io/cshop/anaconda.

The development and production environments use a package management
system named 'eups'. In the introductory installation below, none of
the interesting features of eups are used, but it becomes very useful
once you need to maintain multiple versions of packages, and packages
with dependencies.

..todo:: Find or write intro document on eups: why use it and how?

Fetching the pieces
-------------------

The simplest way to start is to run the simple bootstrapping script
available at *XXX* (for now, in the
gitolite@pfs.ipmu.jp:ics_mhs_config repo, in bin/bootstrap_mhs). This
installs development versions of the core MHS products in `~mhs`, and
arranges for logs and image files to also be saved in that
directory. If you prefer a different root directory, pass the `-P`
argument to `bootstrap_mhs`.

The script starts by installing the latest tagged version of eups
(from git@github.com:RobertLuptonTheGood/eups).

It then installs all the current MHS hub and actor
repositories. Currently these are::

    git clone gitolite@pfs.ipmu.jp:ics_config
    git clone gitolite@pfs.ipmu.jp:tron_tron
    git clone gitolite@pfs.ipmu.jp:tron_actorcore
    git clone gitolite@pfs.ipmu.jp:ics_actorkeys
    git clone gitolite@pfs.ipmu.jp:ics_testaActor

There will be a `source` command shown at the bottom of all that
output. If you are not already using `eups`, you will want to add that
to your login scripts, and you will need to run it now. Something
like::

    source $ICS_ROOT/products/eups/bin/setups.{sh,csh,zsh}

Two versions of each product are installed. One tagged version is
installed into the eups data store (`~mhs/products/`), and the current
git master is installed into a `~mhs/devel` directory).

Running the ICS MHS hub
-----------------------

The `ics_testaActor` product is a sample actor, and setting it up has
the useful side-effect of setting up all the MHS parts at once. If
`eups` is correctly configured, `setup ics_testaActor` will do that,
and return silently.

The tron hub itself is a long-running process. Start it with `tron
start`, which should be boring. `tron stop` will stop it if you need
to.


Running the ICS MHS actors
--------------------------

There is currently just one sample and too-simple actor: `testaActor`.
Before starting any actors, it might be useful to launch a (very)
simple tk-based console. Actually, for reasons which will be cmade
clear later, start two::

    hubclient &
    hubclient &

That should pop up a tk window, with some chatter from the connection
to the hub. In production, actors are started with the `stageManager`
wrapper script, like::

    stageManager testa start

For development, you tend to run them form with `ipython` or the like.
When an actor is started, it connects to a single published hub
port, and tells the hub to launch a connection back to itself. The
slightly cryptic output from all this should appear in the
hubclient window.

_Aside_: the hub and actors are currently configured to only connect
to and listen for `localhost` connections. In general they can be
anywhere, but we should discuss security before opening anything up.

Operating the ICS actors
------------------------

The connected actors can now be commanded from, say, a hubclient. At
the bottom of the hubclient windows is a text field where you can
enter direct commands. The syntax is a) the name of an actor and b)
the command. For instance, send `testa help` or `testa status`, or `hub
status`. Note in `testa help` the `expose` and `centroid` commands,
and take a couple of "exposures"::

    testa expose bias
    testa expose object expTime=2.0

In the `hubclient` you are sending the commands from, you should see
responses, including a filename keyword. There should, in fact, be
real files on disk. 

The other `hubclient` does not show those keywords. The current
configuration arranges for each connection to only see the responses
to the commands it sends. The reason for this choice will be more
obvious when you send the `centroid` command, which returns an encoded
array of 4000 (x,y) centroids::

    testa centroid expTime=0.5

Development
-----------

This bootstrap installation is just that: just enough to get a running
system going. I have not linked in the protocol documentation yet, and
many SDSS systems (authentication, alarms, image directory and
filename sequence encapsulation, standard FITS header generation,
etc.) have either been stubbed out or turned off.

One thing I will point out now. You can create a complete new actor
from a template using the `genActor` shell command. Cd to, say,
`~mhs/devel` and invoke, say::

  genActor mytest

then cd into the new directory, invoke `setup -v -r .` to setup all
the runtime dependencies. Start it with `stageManager mytest start`
and send commands. You can edit the files in `python/mytest/Commands/`
and dynamically reload the new code and commands by sending `mytest
reload`.

Chapter II has more development details.


Chapter II
----------

Yeah, yeah, yeah....
