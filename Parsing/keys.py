__all__ = ['eatAVee', 'eatAString',
           'parseKV', 'parseKVs',
           'parseASCIIReply',
           'parseRawReply']

""" Parsing utilities.

- Keywords can have zero or more comma-delimited values.
- The values are either quoted strings or unparsed tokens.
- Strings can be single- or double-quote delimited with internal quotes backslash-escaped. Non-escape
  backslashes within a string need to be backslash-escaped themselves.

- When parsed from a string, keywords are delimited by semicolons.

"""

import exceptions
import re

import CPL
from RO.Alg import OrderedDict
from Exceptions import ParseException

def eatAVee(s):
    """ Match a keyword value -- a possibly space-padded value ended by a whitespace, a comma, or a semicolon.

    Args:
       s - a string
       
    Returns:
      - the matched value. None if s is just whitespace.
      - any unmatched input, including the terminating character.
    """
    
    # CPL.log('eatAVee', 'called with %s' % (s))

    s = s.lstrip()
    if len(s) == 0:
        return '', ""

    # BEWARE - accept an empty value. 
    if s[0] == ';':
        return '', s

    # String parsing is trickier, let eatAString() handle that.
    if s[0] in "\"'":
        return eatAString(s)

    vEnd = len(s)
    for i in range(len(s)):
        if s[i] in ';, \t\r\n\x0b\x0c':
            vEnd = i
            break

    if vEnd == 0:
        return '', s[vEnd:]
    
    return s[:vEnd], s[vEnd:]


def eatAString(s):
    """ Match a quote-escaped string. 

    Args:
      s - a string, which must begin with a singor- or double- quote.

    Returns:
      - the matched string, or the rest of the line. The quotes are NOT removed.
      - any unmatched input, including the terminating character.

    NOTE:
      If the end of the input string is hit before the leading quote is closed, a closing quote
      is (fairly) silently appended.
      
    """
    
    # CPL.log('eatAString', 'called with %s' % (s))

    if len(s) == 0:
        raise ParseException("unexpected empty string while parsing", leftoverText='')

    startQuote = s[0]
    if startQuote != "\"" and startQuote != "\'":
        raise ParseException("string does not start with a quote", leftoverText=s)

    c = startQuote
    escaping = False
    for i in range(1, len(s)):
        if escaping:
            escaping = False
            continue

        c = s[i]
        
        if c == startQuote:
            return s[:i+1], s[i+1:]
        if c == "\\":
            escaping = True

    # OK, we fell off the end of the string without matching the closing quote.
    # Force the string to look OK so that nobody else needs to deal with a mangled string.
    #
    CPL.log('eatAString', 'adding closing section (esc=%s) to string %r' % (escaping, s))

    if escaping:
        s = "%s\\%s" % (s, startQuote)
    else:
        s += startQuote

    return s, ''

# Match "  key = STUFF"
kv_re = re.compile(r"""
  ^\s*                          # Ignore leading space
  (?P<key>[a-z_][a-z0-9_-]*)    # Match keyword name
  \s*                           # Ignore spaces after keyname
  (?P<delimiter>[=;]|$)
  \s*
  (?P<rest>.*)                  # Match eveything after the delimiter""",
                  re.IGNORECASE|re.VERBOSE)

def parseKV(s):
    """ Try to parse a single KV.
    
    Return:
      { None, None, None } on end-of-input
      { K None rest-of-line } for a valueless keyword or
      { K V rest-of-line }
    """
    
    s = s.lstrip()
    if s == "":
        return None, None, None

    # Try to match for K=V. If we can't, try parsing as a valueless keyword.
    #
    match = kv_re.match(s)
    if match == None:
        raise ParseException(leftoverText=s)

    d = match.groupdict()
    K = d['key']
    rest = d['rest']

    # No equal sign? A valueless keyword.
    #
    if d['delimiter'] != '=':
        return K, None, rest

    # Build a list of values.
    #
    values = []
    while len(rest) != 0:

        # Parse a (sub-)value
        #
        try:
            V, rest = eatAVee(rest)
        except ParseException, e:
            e.prependText(rest)
            raise

        # BEWARE -- eatAVee() can return None for an empty value
        values.append(V)

        # Bail out if we:
        #   - hit EOL
        #
        rest = rest.lstrip()
        if len(rest) == 0:
            break
        
        # Keep gathering subvalues while we find commas.
        #
        if rest[0] == ',':
            rest = rest[1:]
        elif rest[0] == ';':
            rest = rest[1:]
            break
        else:
            break
        
    # Flatten singleton lists.
    if len(values) == 1:
        values = values[0]

    return K, values, rest

def parseKVs(s):
    """ Parse a string of key-value pairs into an OrderedDict .

    Returns:
      - an OrderedDict of keyword values.

    If a keyword has no value, the value is None
    Otherwise the value is a list of parsed values. Note that each value can be None.
    
    """
    
    KVs = OrderedDict()
    rest = s

    while 1:
        try:
            key, values, rest = parseKV(rest)
        except ParseException, e:
            e.setKVs(KVs)
            raise
        
        if key == None:
            break

        # CPL.log('parseKVs', 'key=%r val=%r rest=%r' % (key, values, rest))
        KVs[key] = values

    return KVs

line_midcid_re = re.compile(r"""
  \s*                          # Skip leading whitespace
  (?P<mid>\d+)                 # integer MID
  \s+
  (?P<cid>[a-z0-9_][a-z0-9_.]*)                 # Integer CID. Should be more forgiving.
  \s+
  (?P<flag>[diwe:f>!])           # The flag. Should allow more characters, and check them elsewhere.
  (?P<rest>.*)""",
                     re.VERBOSE | re.IGNORECASE)

line_cidmid_re = re.compile(r"""
  \s*                          # Skip leading whitespace
  (?P<cid>[a-z0-9_][a-z0-9_.]*)  # Integer CID. Should be more forgiving.
  \s+
  (?P<mid>\d+)                 # integer MID
  \s+
  (?P<flag>[diwe:f>!])           # The flag. Should allow more characters, and check them elsewhere.
  (?P<rest>.*)""",
                     re.VERBOSE | re.IGNORECASE)

def parseASCIIReply(s, cidFirst=False):
    """ Try to parse a string into a dictionary containing:
         - mid   - the ICC's MID
         - cid   - the ICC's CID
         - flag  - the reply's flag character
         - KVs   - an OrderedDict of (key, value)s
    
        Returns that dictionary, or raises RuntimeError.

        If a reply line cannot be parsed at all, insert the entire line into the key 'RawLine'.
        If a reply line cannot be completely parsed, insert the unparsed section into the key 'UNPARSEDTEXT'.
    """

    if cidFirst:
        match = line_cidmid_re.match(s)
    else:
        match = line_midcid_re.match(s)
        
    if match == None:
        d = {}
        d['mid'] = 0
        d['cid'] = 0                    # or 'hub' or '.hub'?
        d['flag'] = 'w'
        d['RawText'] = s

        kvs = OrderedDict()
        kvs['RawLine'] = [CPL.qstr(s)]
        d['KVs'] = kvs
        return d

    d = match.groupdict()

    try:
        KVs = parseKVs(d['rest'])
    except ParseException, e:
        KVs = e.KVs
        leftoverText = e.leftoverText

        # In this case, quote the offending text.
        KVs['UNPARSEDTEXT'] = [CPL.qstr(leftoverText)]
    except Exception, e:
        CPL.log("parseASCIIReply", "unexpected Exception: %s" % (e))
        KVs = OrderedDict()
        KVs['UNPARSEDTEXT'] = [CPL.qstr(d['rest'])]
        
    d['KVs'] = KVs
    d['RawText'] = s
    del d['rest']
    
    return d

def parseRawReply(s, keyName="RawText"):
    """ Return a Reply with the entire input string saved in the given keyName keyword.

    Does not make any effort to determine command success, termination, failure, etc.
    """

    d = {}
    d['mid'] = 0
    d['cid'] = 0 
    d['flag'] = 'i'

    CPL.log('parseRawReply', 'consumed :%r:' % (s))
    
    kvs = OrderedDict()
    kvs[keyName] = [CPL.qstr(s)]
    d['KVs'] = kvs
    d['RawText'] = s
    return d

def testParsing():
    OKtests = ("",
               "o",
               "expose",
               "expose boo",
               "expose boo=",
               "expose boo='bar'",
               "expose a b c=def h",
               "e 1 2 3",
               "msg let me 'abc def' xx=123 yy='oh let me be'")

    NGtests = ("'",
               "abc'=1",
               "shortString='abcd",
               "eol=2,3,")
    
    for t in OKtests:
        r = parseKVs(t)
        print "OKtest = %s" % (t)
        print "output = %s" % (r)
        print
        
    for t in NGtests:
        print "NGtest = %s" % (t)
        try:
            r = parseKVs(t)
            print "output = %s" % (r)
        except Exception, e:
            print "exception = %s" % (e)
            
        print

def testMatching():
    pass

if __name__ == "__main__":
    testParsing()
    testMatching()
             
