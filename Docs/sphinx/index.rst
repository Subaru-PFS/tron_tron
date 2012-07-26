.. Tron documentation master file, created by
   sphinx-quickstart on Wed Jul 25 00:15:35 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Overview
========

Control software for complex and distributed systems is
challenging. One approach is to couple the individual pieces loosely
with light-weight protocols, while enforcing public interfaces with
well-typed contracts. This is especially good for distributed
development, where you want day-to-day flexibility and need reliable
integration. 

Tron was developed as a relatively simple distributed communication
system, designed to encourage independant development by hardware
component or software module developers, and to minimize hurdles to
their eventual integration.

The only significant requirement on these components is that they
publish a dictionary fully describing a set of keywords which defines
the state of the software or hardware module, and that in operation
they keep those keywords updated.


The implementation can be sketched out:

 - "commanders" send commands to "actors", via a central hub. Actors can also be commanders.
 - actors reply to commands and generate status keywords, also via the hub.
 - actors are required to completely describe their state by
   generating status keyword whenever their state changes.
 - by default the hub broadcasts all actor traffic to all commanders.
 - command and replies are sent using line-oriented ASCII
   protocols.
 - there is no particular language requirement on commanders or
   actor, except that the keyword dictionary must be published as a
   python declaration. Also, we only have sample implementations in python.
 - many actors and commanders can be run one one host, or they can be
   distributed on a network.

The net result is that all commanders connected to the hub passively
always have an up-to-date view of all actors.

.. toctree::

 PFS
 summary
 toyMain


.. Indices and tables
.. ==================
..
.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`

