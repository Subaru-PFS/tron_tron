Protocol examples
================

Usually the communication protocol is hidden behind library routines,
as seen in the :ref:`Hello, World <toyActor>` example, 
but some people like to know the details. To make this a little less
abstract, we'll walk through what happens when a commander sends
commands to some actors through the hub. When commanders connect to
the hub they either negotiate or are assigned some commander
name. Assume a human has connected, and been given the name
"User.Joe". Joe then sends two commands:

 - ``neon on`` to the ``lamp`` controller
 - ``expose time=30`` to ``spec2``, the second spectrograph.

Using the python library from the example, those would be written as::

 self.actor.cmdr.call(actor='lamp', cmdStr='neon on')

or::

 self.actor.cmdr.call(actor='spec2', cmdStr='expose time=30', timeLim=60)
 

Commands
--------

The command protocol into the tron hub is a line-oriented ASCII
protocol, with only a little imposed structure. The hub passes the
actual command strings unchanged, and maintains a mapping between each
connection's unique serial IDs::

 commandSerialNum commanderName targetActor commandString

For our two examples, Joe's program would send::

 1 User.Joe lamps neon on
 2 User.Joe spec2 expose science time=30.0

When the hub forwards these commands on to the target actors, it removes
the name of the actor and changes the serial number to the next
available one for the given actor. So, for example::

 134 User.Joe neon on

and::

 967 User.Joe expose science time=30.0


Reply flags
^^^^^^^^^^^

A actor replies to commands with the actorSerialNum the hub sent, and
a single status flag::

 actorSerialNum flag [keywords]

Each command **must** be finished with exactly one reply with one of
the following two flags::

 :   - successful command completion
 f   - command failure

Optionally, each command can send along other, non-terminating,
replies::

 i   - "intermediate" reply.
 w   - "intermediate" reply indicating some warning.


For the first example, when the lamp controller received::

 134 User.Joe neon on

the library would parse that into a `cmd` object which would be passed
into a callback function. If all went well the replies might be::

 134 i text="turning neon lamp on"
 134 i neon=on; hgCd=off
 134 :

Using the python library, a programmer would write those as::

 cmd.inform('text="turning neon lamp on"')
 cmd.inform('neon=%s; hgCd=%s" % (neon.state, hgcd.state))
 cmd.finish()

For the second example above, the spec2 actor might reply to::

 967 User.Joe expose science time=30.0

with::

 967 i exposureID=123
 967 i exposureState="Flushing"
 967 i exposureState="Integrating"; shutter="open"
 967 i exposureState="Reading"; shutter="closed"
 967 : exposureState="Done"; filename="PFSA000012302.fits"


When actors send commands
^^^^^^^^^^^^^^^^^^^^^^^^^

So why does the commanderName get passed in to the hub and down to
actors? Well, if an actor also sends commands to other actors, it
is useful to track where the triggering command originally came
from. So, if the spec2 actor needed to adjust telescope focus, it
would send something like::

 32 User.Joe.spec2 telescope offset focus -10

When actors generate unsolicited status
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

And how do actors update their status outside of commands? They use a
serial number of 0. For example, the spec2 controller might send::

 0 w ccdTemp=-75.3

Finally
^^^^^^^

The serial numbers get (un-)translated each time replies go through
the hub, so that a command sender can associate replies with its own
command IDs. To allow for errors and other special cases, the source
of the reply is also added. So for the above commands the original
User.Joe commander would see::

 User.Joe 1 lamps i text="slewing to 90,30"
 User.Joe 1 lamps i neon=on; hgCd=off
 User.Joe 1 lamps :

 User.Joe.spec2 32 telescope : focus=1000

 User.Joe 2 spec2 i exposureID=123
 User.Joe 2 spec2 i exposureState="Flushing"
 User.Joe 2 spec2 i exposureState="Integrating"; shutter="open"
 User.Joe 2 spec2 i exposureState="Reading"; shutter="closed"
 User.Joe 2 spec2 : exposureState="Done"; filename="PFSA000012302.fits"




