Installing the MHS and actors
=============================

The MHS system is maintained as a collection of git repositories in
the gitolite collection at pfs.ipmu.jp. The central parts are:

 - the 'tron' hub repo.
 - an 'actorcore' infrastructure library repo.
 - several repositories for individual "actors", each of which
   encapsulates a subsystem or provides some control logic.

All of these require a recent python. 2.6 is probably OK, 2.7
certainly is. The actors also require twisted, numpy, and
pyfits. These are common enough packages that we think we can expect
them to be installed on the machines. But the HSC/LSST stack does
supply all of them, so we can do that if necessary.

All of these currently use a package versioning system named 'eups',
which is used by the HSC reduction pipeline. In the introductory
installation below, none of the interesting features of eups are used,
but it becomes very useful once you need to manage multiple versions
of packages with dependencies.

Fetching the pieces
-------------------

To start with, I will describe a manual installation of live git
versions into a single directory tree, with all programs running on
that same host. And to expose the degree of hidden magic involved all
the steps are written out. 

Choose some root directory, and under that::

    export ICS_ROOT=$PWD/ics # or for csh folks: setenv ICS_ROOT $PWD/ics
    mkdir -p $ICS_ROOT/devel $ICS_ROOT/data
    cd $ICS_ROOT/devel

If you do not yet have a eups tree, fetch and install that first::

    git clone -b 1.2.33 git@github.com:RobertLuptonTheGood/eups 
    (cd eups; ./configure --with-eups=$ICS_ROOT/products --prefix=$ICS_ROOT/products/eups; make install)

You almost certainly want to add the `source` command at the bottom of
that output to your login scripts. In any case, run it now::

    source $ICS_ROOT/products/eups/bin/setups.sh

Fetch all the MHS hub and actor repositories:

    git clone gitolite@pfs.ipmu.jp:ics_mhs_tron
    git clone gitolite@pfs.ipmu.jp:ics_mhs_actorcore
    git clone gitolite@pfs.ipmu.jp:ics_mhs_actorkeys
    git clone gitolite@pfs.ipmu.jp:ics_mhs_mcsActor
    git clone gitolite@pfs.ipmu.jp:ics_mhs_mpsActor
    git clone gitolite@pfs.ipmu.jp:ics_mhs_pficsActor


