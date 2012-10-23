.. _toyActor:

Hello, World, or a Toy actor
==============================

This is a nearly complete example of a working actor. One main
boilerplate file, and one file defining and implementing some
commands. Execute the main file, and you can send commands to this
actor either directly or via the hub.

Toy Main
--------

The main actor program sets up connections to the hub, arranges for
the command definitions to be loaded and registered with a parser, and
wires up and starts a twisted reactor. Incoming commands are
automatically dispatched. Note that this file is mostly boilerplate
and would not need to be modified significantly.

.. literalinclude:: toy_main.py
   :linenos:


Toy Commands
------------

Files in the Commands subdirectory are automatically loaded, and their
command definitions registered with the parser: for each of the items
in `self.vocab`, 

Note that the actor infrastructure provides a 'reload' command which
lets you dynamically reload these command files while the actor is
running. In practice, actors can be developed without being restarted.


.. literalinclude:: ToyCmd.py
   :linenos:

.. todo:: Put tron and the toyActor in some PFS-accessible git repo.
.. todo:: consolidate the three underlying library products into one.
.. todo:: make a one-click installer 

