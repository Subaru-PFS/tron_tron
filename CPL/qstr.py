__all__ = ['qstr']

def qstr(o, equotes=None, tquote='"'):
    """ Put a string representation of an object into quotes and escape it minimally.
    
    Return the string wrapped in tquotes.
    Escape all the characters in equotes, as well as backslashes. If equotes are
    are not defined, use tquote.
    
    Basically, 
       o  -> "str(o)"
       \  -> \\
       eq  -> \eq
    """
  
    s = str(o)
    
    # Always quote backslashes _first_.
    #
    if equotes == None:
        if tquote == None:
            return s
        equotes = '\\' + tquote
    else:
        equotes = '\\' + equotes    
     
    # Should compare with a clever RE scheme:
    #   matches = match_all(equotes)
    #   '\\'.join(match pieces)
    #
    for equote in equotes:
        equote_repl = "\\" + equote
        idx = 0
        while 1:
            dq = s.find(equote, idx)
            #        sys.stderr.write("dq=%d idx=%d len=%d\n s=%r" % (dq, idx, len(s), s))
            if dq == -1:
                break
        
            s = ''.join((s[:dq], equote_repl, s[dq+1:]))
            idx = dq + 2
        
    if tquote:
        return ''.join((tquote, s, tquote))
    else:
        return s
            

if __name__ == "__main__":
    tests = ('',
             '"',
             '""',
             "''",
             "'",
             "\'",
             '\"',
             '\\',
             '\"',
             'abcdef',
             'abc"\\')
    
    for t in tests:
        qt = qstr(t)
        try:
            e = eval(qt)
        except Exception, e:
            print "===== NE: %s" % (t)
            print "        : %s" % (qt)
            continue
            
        if t == e:
            print "===== OK: %s" % (qt)
        else:
            print "===== NG: %s:" % (t)
            print "        : %s:" % (qt)

    print
    print
