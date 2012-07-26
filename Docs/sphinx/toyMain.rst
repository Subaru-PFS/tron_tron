
Hello, World
=====================

This is a nearly complete example of a working actor -- 

Toy Main
--------

The main actor program sets up connections to the hub, arranges for
the command definitions to be loaded and registered with a parser, and
wires up and starts a twisted reactor. Incoming commands are
automatically dispatched. Note that this file is mostly boilerplate
and would not need to be modified significantly.

.. literalinclude:: toy_main.py
   :linenos:


ToyCommands
------------

Files in the Commands subdirectory are automatically loaded, and their
command definitions registered with the parser.

Note that the actor infrastructure provides a 'reload' command which
lets you dynamically reload these command files while the actor is
running. In practice, actors can be developed without being restarted.


.. literalinclude:: ToyCmd.py
   :linenos:

