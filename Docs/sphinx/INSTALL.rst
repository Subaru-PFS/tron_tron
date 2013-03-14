Installing the MHS and actors
=============================

The MHS system is maintained as a collection of git repositories in
the gitolite collection at pfs.ipmu.jp. The central parts are:

 - the 'tron' hub repo.
 - an 'actorcore' infrastructure library repo.
 - several repositories for individual "actors", each of which
   encapsulates a subsystem or provides some control logic.
 - an 'actorkeys' repo, which contains the published keyword APIs for
   all the individual actors.

All of these require a recent python. 2.6 is probably OK, 2.7
certainly is. The actors also require twisted, numpy, and
pyfits. These are common enough packages that we can probably expect
them to be installed on the machines. 

The system uses a package versioning system named 'eups'. In the
introductory installation below, none of the interesting features of
eups are used, but it becomes very useful once you need to maintain
multiple versions of packages, and packages with dependencies.

Fetching the pieces
-------------------

To start with, I will describe a manual installation of live git
versions into a single directory tree, with all programs running on
that same host. And to expose the degree of hidden magic involved all
the steps are written out. 

Make some root directory for all the MHS development and output
files. For this introduction, I'll assume that the root directory is
`~/mhs` and that development tree for the git clones is
`~mhs/devel`. Ill show how to customize this below)::

    cd
    mkdir -p mhs/devel 
    cd mhs/devel

If you do not yet have a eups tree, fetch and install that first::

    git clone -b 1.2.33 git@github.com:RobertLuptonTheGood/eups 
    (cd eups; ./configure --with-eups=$ICS_ROOT/products --prefix=$ICS_ROOT/products/eups; make install)

You almost certainly want to add the `source` command shown at the
bottom of that output to your login scripts. In any case, run it now::

    source $ICS_ROOT/products/eups/bin/setups.sh

Fetch all the MHS hub and actor repositories:

    git clone gitolite@pfs.ipmu.jp:ics_mhs_actorcore
    git clone gitolite@pfs.ipmu.jp:ics_mhs_actorkeys
    git clone gitolite@pfs.ipmu.jp:ics_mhs_tron
    git clone gitolite@pfs.ipmu.jp:ics_mhs_mcsActor
    git clone gitolite@pfs.ipmu.jp:ics_mhs_mpsActor
    git clone gitolite@pfs.ipmu.jp:ics_mhs_pficsActor

Register all the local repos as containing the latest, current,
version of each::

    for r in ics*; do eups declare -c -r $r; done

Running the ICS MHS hub
-----------------------

The tron hub is a long-running process. Given the eups configuration
above, start it with `tron start`.





