import time

from client import *

run()

for i in range(100):
    call('msg', 'boom %d' % (i))
    print "done: %d" % (i)
    
