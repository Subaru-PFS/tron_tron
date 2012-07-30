Overview
--------

Control software for complex and distributed systems is
challenging. One approach is to couple the individual pieces loosely
with light-weight protocols, while enforcing public interfaces with
well-typed contracts. This is especially useful for distributed
development, where you want day-to-day flexibility unencumbered by
complexity, but also hope for reliable integration. 

There is also value in decomposing a system's components into
general-purpose modules. For example, if a camera can have several
uses, it is logical to try to factor it out as its own
device. Modularization can also help with testing and maintenance, by
making hardware more directly accessible.

Tron was developed as a relatively simple distributed communication
system, designed to encourage the use of independent hardware
components and software modules. The only significant requirement is
that each component or program must come with a published dictionary
describing status keywords which fully define the state of the module,
and that in operation those keywords are kept updated.

The implementation can be sketched out:

 - "commanders" send commands to "actors", via a central hub. 
 - actors reply to commands and generate status keywords, also via the hub.
 - actors can also be commanders.
 - by default the hub broadcasts all actor traffic to all commanders.

 - actors are required to generate status keyword whenever their state changes.
 - command and replies are sent using line-oriented ASCII protocols.
 - there is no particular language requirement on commanders or
   actor, except that the keyword dictionary must be published as a
   python declaration. Also, we only have sample implementations in python.
 - many actors and commanders can be run one one host, or they can be
   distributed on a network.

The net result is that all commanders connected to the hub passively
always have an up-to-date view of all actors.
