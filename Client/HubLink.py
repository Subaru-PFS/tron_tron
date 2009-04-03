#!/usr/bin/env python

__all__ = ['Command',
           'ASCIICmdEncoder',
           'ClientNub',
           'HubLink']
           
""" The lower level of the client interface.
    Negotiates between the hub (via a socket, currently), and the client layer, using Queues.

    The upper layer passes a queue and an optional command:
       call(tgt, cmd, queue)
       listen(queue)

    We register the filter and send the command. Then every response from the hub
    is passed to the filter; if the filter accepts the response it is put into the queue.

    The filters are passed back to the upper layer, and are what identify individual
    calls.
"""

import atexit
import imp
import inspect
import pprint
import socket
import sys
import time
import traceback
import Queue
import CPL

import IO.PollHandler
import IO.IOHandler
import FilterQueue

import Hub.Reply.Decoders as Decoders
import Hub.KV.KVDict as KVs
import CommandLink

class Command(object):
    """ Stub Command, sufficient to please ASCIICmdEncoder. """

    def __init__(self, cid, mid, tgt, cmd, **argv):

        self.ctime = time.time()

        # How we want the command identified.
        self.cmdrCid = cid
        self.cmdrMid = mid

        # Who will operate on the command, and the command itself.
        self.actorName = tgt
        self.cmd = cmd

class ASCIICmdEncoder(object):
    """ Stub encoder for client commands. """

    def __init__(self, **argv):
        self.debug = argv.get('debug', 0)
        
    def encode(self, cmd):
        return "%s %s %s %s\n" % \
               (cmd.cmdrMid, cmd.cmdrCid, cmd.actorName, cmd.cmd)
    
class ClientNub(IO.IOHandler):

    def __init__(self, poller, brains, host, port, **argv):
        """ The IOHandler part of a connection which sends commands.
        """
        
        IO.IOHandler.__init__(self, poller, **argv)

        self.brains = brains
        self.inputBuffer = ""
        self.outputBuffer = ""

        self.encoder = argv.get('encoder', self)
        self.decoder = argv.get('decoder', self)
        
        # All active commands that we are aware of, either because
        # we sent them, or because the actor replied to it.
        #
        self.liveCommands = {}
        
        # All active commands that we have sent to the actor.
        #
        self.ourCommands = {}

        self.mid = 1
        self.connect(host, port)
    
    def connect(self, host, port):
        self.host = host
        self.port = port
        
        CPL.log("ClientLink.connect", "connecting to %s:%s" % (host, port))
        
        f = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        f.connect((host, port))
        f.setblocking(0)
        
        self.setInputFile(f)
        self.setOutputFile(f)

    def sendCommand(self, c, debug=0, timeout=None):
        """ Main entry point for sending a command.

        Args:
           c        - a Command to send
           debug    -
           timeout  - number of seconds to wait before failing the command.
        """
        
        # Check whether we can encode the command first:
        #
        if debug > 5:
            CPL.log("ClientHub.sendCommand", "sending command %s" % (c))
        ec = self.encoder.encode(c)
        self.__registerCmd(c)

        timer = None
        if timeout != None:
            timer = self.makeTimer(timeout, self.copeWithTimeout, c)
        self.queueForOutput(ec, timer=timer)

    def copeWithTimer(self, timer):
        """ Accept a timer event.

        Args:
            timer     - a Timer

        We get called whenever an PollHandler goes off on a regular callback timer.
        """

        q = timer['token']
        q.put(timer['time'])
        
    def copeWithTimeout(self, timer):
        """ Accept a timout event.

        Args:
            timer     - a Timer

        We get called whenever an PollHandler goes off due to a command timeout.
        We close out the command and synthesize a failing Reply.
        """

        key = timer['token']
        cmd = self.liveCommands.get(key, None)
        
        if cmd:
            del self.liveCommands[key]
            self.brains.copeWithTimeout(cmd)
        else:
            CPL.log("hubLink", "timeout w/o cmd: %s" % (timer))
            
        return cmd

    
    def copeWithInput(self, s):
        """ Incorporate new input: buffer it, then extract and operate on each complete reply.

        Args:
           s   - the new, but still unbuffered, input.
        """

        if self.debug > 6:
            CPL.log('Nub.copeWithInput', "read: %s" % (s))

        # Find and execute _every_ complete input.
        # The only time this function gets called is when new input comes in, so we
        # have no reliable mechanism for deferring input. If we need to, we could
        # adapt the PollHandler to query for unconsumed input. Hmm, maybe not.
        #
        while 1:
            reply, leftover = self.decoder.decode(self.inputBuffer, s)
            s = None
            self.inputBuffer = leftover
            if reply == None:
                break

            cmd = self.__getCmdForReply(reply)
            self.brains.copeWithInput(reply)
        
    def keyForCommand(self, cmd):
        """ Generate an immutable unique key for this command.

        This should perhaps go into the encoder?
        """

        return (str(cmd.cmdrCid), str(cmd.cmdrMid))
    
    def keyForReply(self, reply):
        """ Extract the key for this reply. Must match what .keyForCommand() is doing.

        This should perhaps go into the decoder?
        """

        return (str(reply.cmdrCid), str(reply.cmdrMid)) 


    def flagFinishesCommand(self, f):
        """ Return True if a reply flag completes the command. """
        
        return f in ':fF'

    def timeoutCallback(self, cid):
        """ Called by the IOHandler if the callback timer fires.

        Args:
            cid      - the cid of the command which timed out.
        """

        cmd = self.liveCommands[key]
        del self.liveCommands[key]
        
        self.brains.cmdTimeout(cmd)
        
        
    def __registerCmd(self, cmd):
        """ """
        
        self.mid += 1
        key = self.keyForCommand(cmd)
        
        if self.debug > 3:
            CPL.log("Nub", "registering key=%s for %s" % (key, cmd))
        if self.liveCommands.has_key(key):
            raise RuntimeError("Duplicate command key for %s: %s" % (self, key))

        self.liveCommands[key] = cmd

    def __getCmdForReply(self, reply):
        """ Look for a command that matches the reply. Create one if none exists. """
        
        key = self.keyForReply(reply)
        cmd = self.liveCommands.get(key, None)
        
        if cmd and self.flagFinishesCommand(reply.flag):
            del self.liveCommands[key]
            
        return cmd

class HubLink(object):
    
    def __init__(self, **argv):
        """ Open a single Commander connection to the hub.

        args:
            debug          -
            commandHandler - set if we should accept commands on stdin.
        """

        self.debug = argv.get('debug', 0)
        host = argv.get('host', 'localhost')
        port = int(argv.get('port', 6094))
        
        # Create a PollHandler
        #
        self.poller = IO.PollHandler(debug=self.debug, threaded=True, timeout=0.2)
        
        # Create a connection to the hub and register it.
        #
        decoder = Decoders.PyReplyDecoder(debug=1)
        encoder = ASCIICmdEncoder(debug=1)
        self.toHub = ClientNub(self.poller, self, host, port,
                               name='client', encoder=encoder, decoder=decoder,
                               replyCallback=self.copeWithInput,
                               debug=self.debug)
        self.mids = CPL.ID()
        self.KVs = KVs.KVDict(debug=3)
        
        # A list of filters through which we pass all input from the hub.
        #
        self.filters = []

        # Be simple & stupid: lock everything we do with one big lock.
        #
        self.lock = CPL.LLock(debug=1)
        
        self.fromHub = None
        commandQueue = argv.get('cmdQueue', None)
        testing = argv.get('cmdTesting', False)
        if commandQueue != None:
            if testing:
                self.fromHub = CommandLink.connect(self.poller, commandQueue,
                                                   in_f=None, out_f=None,
                                                   debug=self.debug)
            else:
                self.fromHub = CommandLink.connect(self.poller, commandQueue,
                                                   debug=self.debug)

            self.filters.append(commandQueue)
            
    def run(self):
        """ Called by the Thread start() routine. Probably needs a better try, except wrapper. """

        try:
            self.poller.run()
        except SystemExit, e:
            CPL.log("HubLink.run", "SystemExit: %s" % (e))
            raise
        except Exception, e:
            # I haven't evaluated what all gets raised. So go public.
            raise
        
    def call(self, tgt, cmd, cid=0, q=None, timeout=None,  **argv):
        """ Send a command and create a Queue for the replies.

        Args:
            tgt     - where to send the command
            cmd     - the command to send.
            q       - An optional Queue to put replies on.
            timeout - number of seconds to wait before failing the cmd.
            
        Return:
            the queue upon which replies will be sent.
            
        We build a filter matching the command.
        
        """

        debug = argv.get('debug', self.debug)
        if debug > 0:
            CPL.log("hubLink.call", "tgt=%s, cmd=%s" % (tgt, cmd))
                
        self.lock.acquire(src="call")
        try:
            mid = self.mids.gimme()
        
            command = Command(cid, mid, tgt, cmd, debug=debug)
            if q == None:
                q = FilterQueue.ClientCmdFilter(command, debug=debug)
                self.filters.append(q)
            self.toHub.sendCommand(command, debug=debug)
        finally:
            self.lock.release()
        
        return q

    def timer(self, howLong, **argv):
        """ Arrange for a timed callback.

        Args:
            howLong - number of seconds to wait before triggering
            
        Return:
            the queue upon which the trigger will be sent.
            
        """

        debug = argv.get('debug', self.debug)
        if debug > 0:
            CPL.log("hubLink.timer", "howLong=%s" % (howLong))
                
        self.lock.acquire(src="timer")
        try:
            q = Queue.Queue()
            timer = self.toHub.makeTimer(howLong, self.toHub.copeWithTimer, q)
            self.toHub.addTimer(timer)
        finally:
            self.lock.release()
        
        return q

    def listenFor(self, src, keys, **argv):
        """ Send a command and create a Queue for the replies.

        Args:
            src     - what actor to listen to
            keys    - what keys to listen to.

        Return:
            the queue upon which replies will be sent.
            
        We build a filter matching the command.

        
        """

        debug = argv.get('debug', self.debug)
        if debug > 0:
            CPL.log("hubLink.listen", "src=%s, keys=%s" % (src, keys))
                
        self.lock.acquire(src="call")
        try:
            q = FilterQueue.ClientFilter(src, keys, debug=debug)
            self.filters.append(q)
        finally:
            self.lock.release()
        
        return q

    def listen(self, f):
        """ Arrange to listen for some externally specified input.

        Args:
           f   - a Filter

        Returns:
           the filter.
        """

        self.lock.acquire(src="listen")
        try:
            self.filters.append(f)
        finally:
            self.lock.release()

        return f
    
    def finishedWith(self, id):
        """ Unregister a filter. """

        self.lock.acquire(src="finishedWith")

        if id not in self.filters:
            CPL.log("HubLink.finishedWith", "no filter: %s" % (id))
            self.lock.release()
            return
        
        try:
            self.filters.remove(id)
        finally:
            self.lock.release()
        
    def copeWithInput(self, reply):
        """ Handle a new Reply by letting all our filters have a chance to accept it. """
        

        if self.debug > 3:
            CPL.log("HubLink", "coping with new reply: %s" % (reply))

        # Let responses from the keys actor be interpreted as keys from the queried actor.
        src = reply.src
        if reply.src[:5] == 'keys.':
            src = reply.src[5:]
        self.KVs.setKVsFromReply(reply, src=src)
        for f in self.filters:
            f.copeWithInput(reply)

