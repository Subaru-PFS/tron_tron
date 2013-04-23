.. _sampleActor:

.. todo:: link from this doc file into a product's code. Right now we
          are copying from mcsActor.

Hello, Camera: a simple actor
=============================

This is a nearly complete example of a working actor. We are using a
snapshot of the MCS camera controller.

Main actor instance and routine
-------------------------------

The main actor program must be a runnable python program file. The
main routine must define a subclass of the ``actorcore.Actor.Actor``
class, create an instance of it, and call its ``.run()`` method.

The instance creation reads a config file, sets up connections to the
:term:`tron` hub, arranges for the actor's command definitions to be loaded and
registered with a parser, and declares which other actors it needs
keyword updates from.

Calling the actor's ``.run()`` method wires up and starts a ``twisted``
reactor, after which commands from the hub are automatically parsed
and dispatched.

Note that this file is mostly boilerplate and would not need to be
modified significantly. That said, the instance is a very good place
to hold links to long-running state (e.g. objects encapsulating hardware)

.. literalinclude:: mcsActor_main.py
   :linenos:


Commands
--------

All files with names ending in ``Cmd.py`` in the ``Commands`` subdirectory
are automatically loaded; if a class with the same name is found it is
instantiated and the ``.vocab`` and ``.keys`` members used to populate the
parser. 

Note that the actor infrastructure provides a ``reload`` command which
lets you dynamically reload these command files while the actor is
running. In practice, actors can be developed without being restarted,
but because of that it is important not to save any context in command objects.


.. literalinclude:: McsCmd.py
   :linenos:

.. todo:: make a one-click installer 

