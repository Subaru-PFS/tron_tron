#!/usr/bin/env python
"""Version of runtui.py that checks the code with pychecker.

History:
2007-07-09 ROwen
"""
import os
import sys
import pychecker.checker
pydir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
sys.path.append(pydir)
import gmech
gmech.run()
