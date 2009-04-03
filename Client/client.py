#!/usr/bin/env python

"""
   The client interface provides both a Commander and an Actor link to the hub, and the
   following API:

   Synchronous calls:
       - res = call(tgt, command)
       - res = waitForAny(src, keys=None)
       - res = waitForAll(src, keys=None)

   Asynchronous callbacks:
       -       callback(tgt, command, callback=None, dribble=False)
       -       listenForAny(src, callback, keys=None)
       -       listenForAll(src, callback, keys=None)

   Register vocabulary:
       - res = registerWord(word, function, help)
       - res = registerWords(list of above triples)

   Timers:
       - sleep(secs)
       - timer(secs, callback)
       
   The dirty work is done with, horrors, threading. I hate and fear threading. The problems are
   mitigated by splitting communications into upper and lower layers, with the two connected by
   Queues.

   The external, lower, layer (PollHandler + IOHandlers) is run within
   a single thread. Each of the API calls above generates a Queue back to the lower layer, and the
   asynchronous calls generate a new thread.

   A certain amount of intelligence needs to be put into the lower layer. That is to
   filter what is sent to our layer with passed chunks.
"""

__all__ = ['run', 'call', 'callback', 'listenFor', 'waitFor', 'timer']

import signal
import threading
import Queue
import time

from Client import HubLink
from RO.Alg import OrderedDict
import CPL

interpreter = 0

class CmdResponse(object):
    pass

class CmdQueueReader(threading.Thread):
    """ Arrange a free running thread to read commands from the hub and dispatch
        them to a given handler.
    """
    
    def __init__(self, queue, handler, **argv):
        """
        Args:
           queue   - the Queue to wait on.
           handler - the function to pass the item from queue to.
        """
        
        self.debug = 0
        if argv.has_key('debug'):
            self.debug = argv['debug']
            del argv['debug']
            
        threading.Thread.__init__(self, **argv)
        self.setName('cmdTop')
        self.setDaemon(True)

        self.queue = queue
        self.handler = handler

        self.start()        

    def run(self):
        while 1:
            if self.debug > 0:
                CPL.log("cmdQueue", "run size=%d" % (self.queue.qsize()))

            cmd = self.queue.get()
            if self.debug > 1:
                CPL.log("cmdQueue", "read queue item")
                
            self.handler(cmd)

def init(**argv):
    global printStyle

    printStyle = 'full'
    
    name = argv.get('name', 'client')
    CPL.setID(name)

    signal.signal(signal.SIGINT, keyboard)
    
    hubLink = HubLink.HubLink(**argv)
    __builtins__['hubLink'] = hubLink

    CPL.log('client.init', 'hubLink=%s' % (hubLink,))

def run(**argv):
    #
    # I don't see how this can be run multiple times because the thread
    # can only be started once.
    #
    if not __builtins__.has_key('hubLink'):
        init(**argv)
        
    hubThread = threading.Thread(name="poller", target=hubLink.run)
    background = argv.get('background', True)
    
    if background:
        hubThread.setDaemon(True)
    try:
        hubThread.start()
    except SystemExit, e:
        CPL.log('client.run', 'got SystemExit')
        raise
    except:
        raise
    
    
def _run(**argv):
    """ Start the connection to the hub and set up all the plumbing for later calls.

        Defines the 'hubLink' global.
    """
    global printStyle

    printStyle = 'full'
    
    name = argv.get('name', 'client')
    background = argv.get('background', True)
    
    CPL.setID(name)

    signal.signal(signal.SIGINT, keyboard)
    
    hubLink = HubLink.HubLink(**argv)
    __builtins__['hubLink'] = hubLink
    hubThread = threading.Thread(name="poller", target=hubLink.run)

    CPL.log('client.run', 'hubLink=%s' % (hubLink,))

    if background:
        hubThread.setDaemon(True)
    try:
        hubThread.start()
    except SystemExit, e:
        CPL.log('client.run', 'got SystemExit')
        raise
    except:
        raise
    
def keyboard(*argl):
    """ Handle keyboard interrupts.

    This would be nice, if only I had rewrittent the readline module to operate
    asynchronously.
    """
    
    raise KeyboardInterrupt

def call(tgt, cmd, debug=0, cid=0, timeout=None):
    """ Send cmd to tgt. Wait for cmd to complete.

    Args:
       tgt      - who to send the command to. e.g. 'dis', or 'tcc'
       cmd      - the command to send.
       
    Returns:
       TBD. Everything. Something like:
          { 'ok' : whether command succeeded
            'keys' : the parsed keys. Lazy evaluation.
            'lines' : the parsed lines. Lazy evaluation.
          }

    major issues:
       - KeyboardInterrupt aren't caught, so there is no way to stop a call()
       
    """

    # We do want to block, so just call, gather all the responses, then return.
    #
    q = hubLink.call(tgt, cmd, debug=debug, cid=cid, timeout=timeout)

    if debug > 3:
        CPL.log("call", "back from hubLink.call")
        
    res = CmdResponse()
    lines = []
    KVs = OrderedDict.OrderedDict()
    
    while 1:
        # resp is:
        #
        resp = q.get()
        
        if debug > 3:
            CPL.log('call', 'get: %s' % (resp,))
        lines.append(resp)
        KVs.update(resp.KVs)
        
        flag = resp.flag
        if flag == ':':
            res.ok = True
            break
        if flag in 'fF':
            res.ok = False
            break

    res.lines = lines
    res.KVs = KVs
    hubLink.finishedWith(q)
    
    if interpreter:
        for l in res.lines:
            print l.pretty()
        if res.ok != True:
            print "FAILED"
    else:
        return res

def getKeys(actor, keyList):
    """ Request keys for a given actor, and optionally convert them.

    Args:
       actor    - the actor whose keys we want.
       keyList  - a list of pairs. The first item in the pair is the key name, and the
                  second item is the converter (None does not convert)

    Returns:
       - a dictionary of the keys and their (possibly converted) values.
    """

    keyNames = [i[0] for i in keyList]
    ret = call('keys', 'getFor=%s %s' % (actor, ' '.join(keyNames)))

    retKeys = ret.KVs
    haveKeys = retKeys.copy()

    for k, cvt in keyList:
        if cvt != None:
            haveKeys[k] = cvt(haveKeys[k])

    return haveKeys

class Callback(threading.Thread):
    """ Arrange for input from a Queue to be read and dispatched asynchronously.

    Args:
        q         - the queue to read from
        callback  - the function to call with the results. Can be None
        dribble   - whether to dispatch each line, or whether to wait until a command finishes.
        checkFlag - whether to even look at the 
    """
    
    def __init__(self, q, callback, dribble, checkFlag=True, debug=0, **argv):
        threading.Thread.__init__(self, **argv)
        self.setDaemon(1)

        self.debug = debug
        self.hubQueue = q
        self.callback = callback
        self.dribble = dribble
        self.checkFlag = checkFlag
        
        self.start()

    def __str__(self):
        return "Callback(id=%s, q=%s, callback=%s, dribble=%s)" % (id(self), self.hubQueue,
                                                       self.callback, self.dribble)
    
    def _del_(self):
        CPL.log("Callback.__del__", "deleting Callback: %s" % (self))
        
    def stop(self):
        """ Stop ourselves and exit.

        We (the thread) are blocked on input from the queue. So we set a flag that
        we test after a read, then generate a dummy element in the queue.

        Of course, this can only be called from a different thread from the one bocked on read...
        """
        
        self.keepRunning = False
        self.hubQueue.put(None)
        
    def run(self):
        CPL.log("Callback.run", "starting Callback: %s" % (self))
        res = CmdResponse()
        lines = []
        KVs = {}
        
        self.keepRunning = True
        while self.keepRunning:
            resp = self.hubQueue.get()
            if self.keepRunning == False:
                break

            if self.debug > 4:
                CPL.log('Callback.run', 'get: %s' % (resp,))

            if self.dribble:
                if self.callback:
                    self.callback(resp)
                else:
                    print resp
            else:
                lines.append(resp.KVs)
                KVs.update(resp.KVs)
                
            if self.checkFlag:
                flag = resp.flag
                if flag == ':':
                    res.ok = True
                    break
                if flag in 'fF':
                    res.ok = False
                    break

        CPL.log("Callback.run", "stopping %s" % (self, ))
        hubLink.finishedWith(self.hubQueue)

        if not self.dribble and self.callback:
            res.lines = lines
            res.KVs = KVs
            self.callback(res)
    
class TimerCallback(threading.Thread):
    """ Arrange for input from a Queue to trigger a callback.

    Args:
        q         - the queue to read from
        callback  - the function to call with the results. Can be None
    """
    
    def __init__(self, q, callback, checkFlag=True, debug=0, **argv):
        threading.Thread.__init__(self, **argv)
        self.setDaemon(1)

        self.debug = debug
        self.hubQueue = q
        self.callback = callback
        
        self.start()

    def stop(self):
        """ Stop ourselves and exit.

        We (the thread) are blocked on input from the queue. So we set a flag that
        we test after a read, then generate a dummy element in the queue.

        Of course, this can only be called from a different thread from the one bocked on read...
        """
        
        self.keepRunning = False
        self.hubQueue.put(None)
        
    def run(self):

        doCallback = False
        self.keepRunning = True
        while self.keepRunning:
            tick = self.hubQueue.get()
            if self.keepRunning == False:
                break

            if self.debug > 4:
                CPL.log('timerCallback.run', 'get: %s' % (tick,))

            doCallback = True
            break

        if self.debug > 0:
            CPL.log("Callback.run", "stopping %s" % (self))
        hubLink.finishedWith(self.hubQueue)

        if doCallback:
            self.callback()

def timer(howLong, callback, debug=0):
    """ Arrange for callback to be called in howLong seconds."""
    
    q = hubLink.timer(howLong, debug=debug)
    cb = TimerCallback(q, callback, debug=debug)

    if debug > 0:
        CPL.log("callback", "launched callback thread for %s" % (cmd))
    
    return cb

def callback(tgt, cmd, callback=None, dribble=False, cid=None, debug=0):
    """ Arrange for a command to be sent, with the result sent asynchronously to the given callback function.

    Args:
       tgt      - who to send the command to. e.g. 'tcc'
       cmd      - the command to send.
       callback - a function that will be called with the command result(s). If None, the output
                  is printed out.
       dribble  - whether to forward each line from tgt individually, or whether to send them all in one chunk.
       
    Returns:
       - the callback instance. The only useful method is .stop().
    """

    if cid:
        q = hubLink.call(tgt, cmd, cid=cid, debug=debug)
    else:
        q = hubLink.call(tgt, cmd, debug=debug)
        
    cb = Callback(q, callback, dribble, debug=debug)

    if debug > 0:
        CPL.log("callback", "launched callback thread for %s" % (cmd))
    
    return cb

def listenFor(src, keys=None, callback=None, debug=0):
    """ Asynchronously wait for any of the given keys to be updated.

    Args:
       src      - the originator of the keys
       key      - a list of keys to wait on. If None, all keys from src will be returned.
       callback - which function to call with the results. If None, the reply is printed out.

    Returns:
       - the callback instance. The only useful method is .stop().
    """
    q = hubLink.listenFor(src, keys, debug=debug)
    cb = Callback(q, callback, dribble=True, checkFlag=False, debug=debug)

    return cb

def waitFor(src, keys=None, debug=0):
    """ Wait for any of the given keys to be updated.

    Args:
       src      - the originator of the keys
       keys     - a list of keys to wait on. If None, any key from src will be returned.
       
    Returns:
       - each Reply that matches the src & key arguments. If a given reply matches several times,
         it is only returned once.

    Issues:
       Running this in a loop will likely let keys pass between calls. 
    """
    q = hubLink.listenFor(src, keys, debug=debug)
    item = q.get()
    hubLink.finishedWith(q)

    return item
    
def waitForAll(src, keylist):
    """ Wait for all of the given keys to be updated.

    Args:
       src      - the originator of the keys
       keylist  - a list of keys to wait on. All the keys must be updated for the function to return.
       
    Returns:
       - a dictionary of the keys and values.
    """

    assert(0 and "waitForAll unimplemented")



def listenForAll(src, keylist, callback):
    """ Asynchronously wait for all of a list of keys to be updated.

    Args:
       src      - the originator of the keys
       keylist  - a list of keys to wait on.
       callback - which function to call with the results.

    Returns:
       - the value.
    """

    assert(0 and "listenForAll unimplemented")

def cmd(s):
    """ Insert a command string into the incoming command stream. """

    hubLink.fromHub.copeWithInput(s + "\n")
    
if __name__ == "__main__":
    run(debug=1)    

