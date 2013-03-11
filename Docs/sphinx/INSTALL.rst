Installing the MHS and actors
=============================

The MHS system is developed as a collection of git repositories at
pfs.ipmu.jp. The central parts are:

 - the 'tron' hub repo.
 - an 'actorcore' infrastructure library repo.
 - several actor repositories.

All currently use a package versioning system named 'eups', which is
used by the HSC reduction pipeline. EUPS is currently not essential,
but I would recommend it.


Fetching the pieces
-------------------

For the moment, I will describe a manual installation into a single
directory tree.
