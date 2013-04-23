Overview
--------

Control software for complex and distributed systems is
challenging. One approach is to couple the individual pieces loosely
with light-weight protocols, while enforcing public interfaces with
well-typed contracts. This is especially useful submodules are
developed independantly: the individual teams want day-to-day
flexibility unencumbered by complexity, but also expecting reliable
integration.

There is also value in decomposing a system's components into
general-purpose modules. For example, if a camera can have several
uses, it is logical to try to factor it out as its own
device. Modularization can also help with testing and maintenance, by
making hardware more directly accessible.

Tron is a centralwas developed as a relatively simple distributed communication
system, designed to encourage independant development of hardware and
software subsystems, and their eventual integration. The only
significant requirement is that each component or program must come
with a published dictionary describing status keywords which fully
define the state of the module, and that in operation those keywords
are kept updated.

The implementation can be sketched out:

 - the :term:`tron` central hub accepts commands received from
   :term:`commanders` and dispatches them to :term:`actors`.

 - actors reply to commands and generate status keywords, also via the hub.
 - by default the hub broadcasts all actor traffic to all commanders,
   but each commander can chose which actors it listens to.
 - by default each actor is also a commander: it can listen to all
   other actors and command them.

 - actors are *required* to generate status keyword whenever their state changes.

 - commands and replies are sent using line-oriented ASCII protocols.
 - tron is implemented in Python, and includes Python modules to
   encapsulate the connections and the command flow.
 - many actors and commanders can be run on one host, or they can be
   distributed on a network.

The net result is that all commanders connected to the hub passively
always have an up-to-date view of all actors.
