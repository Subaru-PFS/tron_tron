__all__ = ['dequote']

import CPL

def dequote(s):
    """ Convert s as a possibly quoted string to an unquoted string.

    If s is quoted, strip the quotes and unescape internal quotes..
    """

    # CPL.log("DEQUOTE", "IN q=%r= s=%r=" % (q, s))

    if s == None:
        return None

    assert type(s) == str
    
    if len(s) >= 2:
        c0 = s[0]
        if c0 not in ('"', "'") or s[-1] != c0:
            return s

        # OK, we have a quoted string. Now build a new string and strip quotes.
        #
        if c0 == '"':
            findQuote = '\\"'
            replaceQuote = '"'
        else:
            findQuote = "\\'"
            replaceQuote = "'"

        sNoQuotes = s[1:-1].replace(findQuote, replaceQuote)
        
        # Then strip escapes.
        #
        sNoQuotes = sNoQuotes.replace('\\\\', '\\')

        # CPL.log("DEQUOTE", "OUT q=%r= s=%r=" % (q, sNoQuotes))

        return sNoQuotes

    return s

if __name__ == "__main__":
    pairs = (('', ''),
             ('""', ''),
             (' ', ' '),
             ('"', '"'),
             ("'", "'"),
             ('\\', '\\'),
             ('"\\\\"', '\\'),
             ('"\""', '"'),
             ("'\''", "'"),
             ('"\a\b\c\d\e\f\g\""', '\a\b\c\d\e\f\g"'),
             ('"abc\"def\\\\ghi"', 'abc"def\\ghi')
             )

    print "testing dequote..."
    for test in pairs:
        s0, s1 = test
        sx = dequote(s0)
        if sx != s1:
            print "mismatch: s0=%r s1=%r got=%r" % (s0, s1, sx)
        else:
            print "ok: %r -> %r" % (s0, sx)
            
