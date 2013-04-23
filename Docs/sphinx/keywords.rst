Keyword dictionary example
--------------------------

An actor's keywords define the externally visible state of the
actor. Anytime the external state of instrument changes, the actor *must*
generate new keywords. The actor is responsible for updating these
keywords, and cannot expect any `status` commands to be issued from
the outside. 

The content and structure of this dictionary is one of the developer's
main responsibilities. It is declared using a typed python dictionary
which is loaded any consuming actor's keyword parser. The dictionary for the
example actor is

.. literalinclude:: mcs_keys.py

and the reference documentation is at 


.. todo:: Get access to APO trac reference docs as HTML. Summarize here.

