  We need a remote client interface for scripting. The scripts would be
both interactive and daemonic. The essential data flow would be:

 - send synchronous commands to the hub
 - send asynchronous commands to the hub
 - accept commands _from_ the hub. 

  Incoming commands are likely to then turn around and send commands
_to_ the hub; the trickiest problem is what to do when we send
synchronous commands, and what to do about state maintained between
commands. 
  The command handler could simply block, which would enforce a
simple, single-threaded, environment. Or each command handler could
run in its own thread; this would require greater care while 

======================================================

  Global commands:

r = call(actor, cmd, [timeout=N])
id = callback(func, actor, cmd, [timeout=N])
   cancelCallback(id)

val = fetchKV(actor, keyName, [asFunc])
vals = fetchKVs(actor, keyNames, [asFuncs])

id = listenFor(actor, keyNames)  
   cancelListenFor(id)

