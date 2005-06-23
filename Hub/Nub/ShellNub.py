__all__ = ['ShellNub']

import os
import resource
import signal
import sys

import CPL
from ActorNub import ActorNub

class ShellNub(ActorNub):
    
    def __init__(self, poller, cmd, **argv):
        ActorNub.__init__(self, poller, **argv)

        self.sig = signal.SIGHUP
        self.shell(cmd)

    def ioshutdown(self, **argv):
        """ Reap our dead child. """

        ActorNub.ioshutdown(self, **argv)
        
        try:
            os.kill(self.pid, self.sig)
        except Exception, e:
            CPL.log("Shell.shutdown",
                    "os.kill(pid=%s, sig=%s) failed with %s" % \
                    (self.pid, self.sig, e))

        pid, status = os.waitpid(self.pid, 0)
        CPL.log("Shell.shutdown", "waitpid returned pid=%s and status=%s" % (pid, status))

    def shell(self, cmd):

        CPL.log('Shell.shell', "%s launching %r" % (self.name, cmd))

        self.cmd = cmd
        p1_i, p1_o = os.pipe()
        p2_i, p2_o = os.pipe()

        pid = os.fork()
        if pid == 0:
            # Child

            os.close(p2_i)
            os.close(p1_o)

            os.dup2(p1_i, 0)
            os.dup2(p2_o, 1)
            os.dup2(sys.stderr.fileno(), 2)

            # Close the rest of the file descriptors
            #
            (fd_max_soft, fd_max_hard) = resource.getrlimit(resource.RLIMIT_NOFILE)
            for fd in range(3, fd_max_soft):
                try:
                    os.close(fd)
                except:
                    pass

            os.execv(cmd[0], cmd)
            assert "child" == "alive"
            
        else:
            # Parent

            os.close(p1_i)
            os.close(p2_o)

            self.pid = pid
            if self.name == None:
                self.ID = "shell-%ld" % (pid)
                self.name = self.ID
                
            self.setInputFile(os.fdopen(p2_i, "r"))
            self.setOutputFile(os.fdopen(p1_o, "w"))
            
            CPL.log('Shell.shell', "launched '%s' %r as pid %d" % (cmd[0], cmd[1:], pid))
            

