#!/usr/bin/env python

import select

p = select.poll()

for i in xrange(1000000):
    p.poll(0.0)

    
