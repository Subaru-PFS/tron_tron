import sys

while 1:
    l = sys.stdin.readline()
    
    print "str(l) = %s" % (l)
    print "repr(l) = %r" % (l)
    print "cnv(l) = %s" % (eval(repr(l)))
    
