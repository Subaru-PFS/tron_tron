#/usr/bin/env python

__all__ = ['IOHandler']

import os
import socket
import time

import CPL

class IOHandler(CPL.Object):
    """ Stub class for IO connections that can be managed by a PollHandler. 
    
    This is the class that is called when input is available to be read and
    when output is known to be possible.
    
    Options:
        readSize: maximum size we read before returning to the poller.
        writeSize: max. size we write before returning to the poller.
        writeMany: if true, write as many queued item as can fit in writeSize
                   if false, only ever send a single queued item.
        in_f: the input file descriptor
        out_f: the output file descriptor.
        
    Bugs:
        in and out should probably not be in the same object.
        
    """

    def __init__(self, poller, **argv):
        CPL.Object.__init__(self, **argv)

        self.poller = poller

        CPL.log("IOHandler.init", "IOHandler(argv=%s)" % (argv))
        
        # The IO size tweaks would mean something for slow network links.
        #
        self.tryToRead = argv.get('readSize', 4096)
        self.tryToWrite = argv.get('writeSize', 4096)
        self.tryToWriteMany = argv.get('writeMany', False)
        self.oneAtATime = argv.get('oneAtATime', False)
        
        self.in_f = self.out_f = None
        self.in_fd = self.out_fd = None
        self.outQueue = []
        self.queueLock = CPL.LLock(debug = (argv.get('debug', 0) > 7))
        self.setInputFile(argv.get('in_f', None))
        self.setOutputFile(argv.get('out_f', None))

        # Some stats
        #
        self.totalReads = 0
        self.totalBytesRead = 0
        self.largestRead = 0
        
        self.totalQueued = 0
        self.maxQueue = 0

        self.totalOutputs = 0
        self.totalWrites = 0
        self.totalBytesWritten = 0
        self.largestWrite = 0
        
    def ioshutdown(self, **argv):
        """ Unregister ourselves """

        why = argv.get('why', "just cuz")
        CPL.log("IOhandler.ioshutdown", "what=%s why=%s" % (self, why))
                
        self.setOutputFile(None)
        self.setInputFile(None)
        
        
    def shutdown(self, **argv):
        """ Unregister ourselves.

        This is meant to be overridden in a subclass.
        """

        self.ioshutdown()
        
    def setInputFile(self, f):
        """ Change the input file. Close and unregister any old file. Register the new one for input. """
        
        if self.debug > 2:
            CPL.log("IOHandler.setInput", "%s changing input %s to %s" % (self, self.in_f, f))

        # Detach and possibly close existing .in_f
        #
        if self.in_f != None:
            self.poller.removeInput(self)
            if self.in_f != f:
                try:
                    self.in_f.close()
                except:
                    CPL.error("IOHandler.setInput", "failed to close input for %s", self)

        # Establish new .in_f
        #
        self.in_f = f
        if f == None:
            self.in_fd = None
        else:
            self.in_fd = f.fileno()
            self.poller.addInput(self)
        
    def setOutputFile(self, f):
        """ Change the output file. Close and unregister any old file. Clear the output queue.

        This should be the only method which adjusts output registration.
        """
        
        if self.debug > 2:
            CPL.log("IOHandler.setOutput", "%s changing output %s to %s. queue=%s" % \
                    (self, self.out_f, f, self.outQueue))

        if self.out_f != None:
            self.poller.removeOutput(self)
            if f != self.out_f:
                try:
                    self.out_f.close()
                except:
                    CPL.error("IOHandler.setOutput", "failed to close output for %s", self)
            
        # Establish new .out_f
        #
        self.out_f = f
        if f == None:
            self.out_fd = None
        else:
            self.out_fd = f.fileno()
        self.outQueue = []

    def getInputFd(self):
        """ Return the file descriptor for our input file. Called by the poller. """
        return self.in_fd
        
    def getOutputFd(self):
        """ Return the file descriptor for our output file. Called by the poller. """

        return self.out_fd

    def makeTimer(self, interval, callback, token):
        """ Create a timer to fire in interval seconds. """

        return self.makeTimerForTime(time.time() + interval, callback, token)
        
    def makeTimerForTime(self, when, callback, token):
        """ Create a timer.

        Args:
            when       - the absolute time (in ticks) to trigger.
            callback   - what function to call when triggered. called as callback(token)
            token      - an additional argument for the callback.

        Returns:
           currently a dictionary.
        """

        timer = {}
        timer['time'] = when
        timer['callback'] = callback
        timer['token'] = token

        return timer
    
    def addTimer(self, timer):
        self.poller.addTimer(timer)
        
    def queueForOutput(self, s, timer=None):
        """ Append s to the output queue. """

        assert s != None, "queueing nothing!"

        self.queueLock.acquire(src='queueForOutput')
        try:
            mustRegister = (self.outQueue == [])

            # Keep the output "lines" separate.
            #
            self.outQueue.append(s)

            # Add any timer.
            if timer != None:
                self.addTimer(timer)
                    
            # Bump the stats.
            self.totalQueued += 1
            if len(self.outQueue) > self.maxQueue:
                self.maxQueue = len(self.outQueue)

            if self.debug > 4:
                CPL.log("IOHandler.queueForOutput",
                        "appended %r to queue (len=%d) of %s" % \
                        (s, len(self.outQueue), self))
            if mustRegister:
                self.poller.addOutput(self)
        finally:
            self.queueLock.release(src='queueForOutput')


    def checkQueue(self):
        """ Check whether we need to (re-) register ourselves with the poller. """

        if self.outQueue != []:
            self.poller.addOutput(self)
            
        
    def readInput(self):
        """ Read what is available to read, buffer that, and consume complete input.

        
        """
        
        error = ""
        readIn = ""
        try:
            readIn = os.read(self.in_fd, self.tryToRead)
        except socket.error, e:
            error = "socket exception %s" % (e,)
            CPL.log("IOHandler.readInput", error)
            readIn = ""
        except os.error, e:
            error = "os exception %s" % (e,)
            CPL.log("IOHandler.readInput", error)
            readIn = ""
        except:
            error = "unknown exception %s" % (e,)
            CPL.log("IOHandler.readInput", error)
            readIn = ""

        if self.debug > 4:
            CPL.log("IOHandler.readInput", "read len=%d %r" % (len(readIn), readIn[:50]))

        # I/O error: by being called, we are told that we have input. But the read
        # showed no available input.
        # So close ourselves.
        #
        
        if readIn == "" and error == "":
            error = "read returned nothing."
            
        if error != "":
            self.shutdown(why=error)
        else:
            self.totalBytesRead += len(readIn)
            self.totalReads += 1
            if len(readIn) > self.largestRead:
                self.largestRead = len(readIn)
                
            self.copeWithInput(readIn)

    def mayOutput(self):
        """ Try to write as much as we should from the queue. 

        We are controlled by two object variables:
            .tryToWrite: the maximum number of bytes we can send before returning control to the poller.
            .tryToWriteMany: whether we can write several queued commands before returning to the poller.

        We send queued items individually, regardless. It might be worth having a .coalesce variable to
        control that. I worry about the system limits being lower than our limits.
        
        """
        
        # Add up what we have written so far.
        totalSent = 0
        
        while True:

            # Try to send a single complete queued item. But truncate if we have to.
            #
            try:
                qtop = self.outQueue[0]
            except IndexError:
                self.setOutputFile(None)
                raise RuntimeError("mayOutput queue for %s is empty!" % (self))

            wlen = min(len(qtop), self.tryToWrite)
            if self.debug > 5:
                CPL.log("IOHandler.mayOutput", "writing len=%d wlen=%d %r" % \
                        (len(qtop), wlen, qtop[:min(wlen, 50)]))
                
            try:
                wrote = os.write(self.out_fd, qtop[:wlen])
            except socket.error, e:
                CPL.log("IOHandler.mayOutput", "socket exception %r" % (e,))
                self.shutdown(why=str(e))
                return
            except os.error, e:
                CPL.log("IOHandler.mayOutput", "os exception %r" % (e,))
                self.shutdown(why=str(e))
                return
            except Exception, e:
                CPL.log("IOHandler.mayOutput", "unhandled exception %r" % (e,))
                self.shutdown(why=str(e))
                return

            totalSent += wrote
            self.totalWrites += 1
            self.totalBytesWritten += wrote
            if wrote > self.largestWrite:
                self.largestWrite = wrote

            self.queueLock.acquire(src='mayOutput')
            try:
                # Either truncate queue[0] or remove it.
                #
                wroteFull = (wrote == len(qtop))
                if wroteFull:
                    self.outQueue.pop(0)
                else:
                    self.outQueue[0] = self.outQueue[0][wrote:]

                # Quit if we have no more to write.
                #
                if self.outQueue == []:
                    self.poller.removeOutput(self)
                    break

                # Quit if we don't want to write any more.
                if (self.oneAtATime and wroteFull):
                    break
                
                if self.debug > 5:
                    CPL.log("IOHandler.mayOutput", "queue len=%d" % (len(self.outQueue)))

                # Quit if we only write one item or if we have written alot.
                #
                if self.tryToWriteMany:
                    if totalSent >= self.tryToWrite:
                        break
                else:
                    break

                self.totalOutputs += 1
            finally:
                self.queueLock.release(src='mayOutput')
        
    def statusCmd(self, cmd, name, doFinish=True):
        """ Send sundry status information keywords.
        """

        cmd.inform('ioConfig=%s,%d,%d,"%s"' % \
                   (CPL.qstr(name),
                    self.tryToRead, self.tryToWrite, self.tryToWriteMany))
        cmd.inform('ioQueue=%s,%d,%d,%d' % \
                   (CPL.qstr(name),
                    len(self.outQueue), self.totalQueued, self.maxQueue))
        cmd.inform('ioReads=%s,%d,%d,%d' % \
                   (CPL.qstr(name),
                    self.totalReads, self.totalBytesRead, self.largestRead))
        cmd.inform('ioWrites=%s,%d,%d,%d,%d' % \
                   (CPL.qstr(name),
                    self.totalOutputs, self.totalWrites, self.totalBytesWritten, self.largestWrite))
        if doFinish:
            cmd.finish()
            
