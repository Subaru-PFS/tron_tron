Example ("Toy") Actor
=====================

Toy Main
--------

The main actor program sets up connections to the hub, arranges for
the command definitions to be loaded and registered with a parser, and
wires up a twisted reactor. Then the reactor is started, after which
incoming commands are automatically dispatched.


.. literalinclude:: toy_main.py
   :linenos:


Toy Commands
------------

Any file in the Commands subdirectory whose name ends with Cmds.py is
automatically loaded, and the command definitions registered with the
parser. 

Note that the actor infrastructure provides a 'reload' command which
lets you dynamically reload these command files while the actor is
running. If you do not wire in any dependancies, etc., actors can be
developed without being restarted.


.. literalinclude:: ToyCmd.py
   :linenos:

