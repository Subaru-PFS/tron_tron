#!/usr/bin/env python

__all__ = ['shellConnect']

import os

def shellConnect(cmd):
    """ Run a command, and return either (in_fd, out_fd, err_fd) or None. """

    try:
        fds = os.popen3(cmd, "w")
    except:
        raise

    return fds
