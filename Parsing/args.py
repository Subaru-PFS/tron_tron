__all__ = ['parseArgs', 'match']

import re

import CPL
from RO.Alg import OrderedDict
from Exceptions import ParseException
from dequote import dequote

from keys import *

# Match "  key = STUFF"
arg_re = re.compile(r"""
  ^\s*                          # Ignore leading space
  (?P<key>[a-z_][a-z0-9_-]*)    # Match keyword name
  \s*
  (?P<delimiter>=)
  \s*                           # Ignore spaces after keyname
  (?P<rest>.*)                  # Match eveything after the delimiter""",
                    re.IGNORECASE|re.VERBOSE)
noarg_re = re.compile(r"""
  ^\s*                          # Ignore leading space
  (?P<key>\S+)                 # Match eveything up to the next WS
  \s*
  (?P<rest>.*)                  # Match eveything after the WS""",
                      re.IGNORECASE|re.VERBOSE)

def eatAVee(s):
    """ Match a keyword value -- a possibly space-padded value ended by a whitespace, a comma, or a semicolon.

    Args:
       s - a string

    Returns:
       - the matched value. None if s is just whitespace.
       - any unmatched input, including the terminating character.
    """

    s = s.lstrip()
    if len(s) == 0:
        return '', ""
    
    # String parsing is trickier, let eatAString() handle that.
    if s[0] in "\"'":
        return eatAString(s)
    
    vEnd = len(s)
    for i in range(len(s)):
        if s[i] in ' \t\r\n\x0b\x0c':
            vEnd = i
            break
        
    return s[:vEnd], s[vEnd+1:]

                                                                                
def parseArg(s):
    """ Try to parse a single KV.
    
    Return:
      { None, None, None } on end-of-input
      { K None rest-of-line } for a valueless keyword or
      { K V rest-of-line }
    """
    
    s = s.lstrip()
    if s == "":
        return None, None, None

    # Try to match for K=V. If we can't, gobble the next non-blank word.
    #
    match = arg_re.match(s)
    if match == None:
        match = noarg_re.match(s)
        if match == None:
            raise ParseException(leftoverText=s)
        d = match.groupdict()
        return d['key'], None, d['rest']

    d = match.groupdict()
    K = d['key']
    rest = d['rest']

    # Parse a value
    #
    try:
        val, rest = eatAVee(rest)
    except ParseException, e:
        e.prependText(rest)
        raise

    return K, val, rest

def parseArgs(s):
    """ Parse a string of command arguments into an OrderedDict .

    Returns:
      - an OrderedDict of keyword values.

    If a keyword has no value, the value is None
    Otherwise the value is a list of parsed values. Note that each value can be None.
    
    cmd a1 a2=1 a3= "2" a4=,
      ->

      args = {'a1' : None,
              'a2' : '1',
              'a3' : '2',
              'a4' : (None,None)
             }
    """
    
    KVs = OrderedDict()
    rest = s

    while 1:
        try:
            key, values, rest = parseArg(rest)
        except ParseException, e:
            e.setKVs(KVs)
            raise
        
        if key == None:
            break

        # CPL.log('parseKVs', 'key=%r val=%r rest=%r' % (key, values, rest))
        KVs[key] = values

    return KVs

def match(argv, opts):
    """ Searches an OrderedDict for matches.

    Args:
      argv - an OrderedDict of options.
      opts - a list of duples to match against. The duple parts are the option name
             and a converter. If the converter is None, the option takes no argument.

    Returns:
      matches   - an OrderedDict of the matched options, with converted arguments.
      unmatched - a list of unmatched options from opts.
      leftovers - an OrderedDict of unmatched options from argv.

    Raises:
      Error     - Any parsing or conversion error.
    """

    # Convert the request duples to an OrderedDict
    want = OrderedDict()
    for o in opts:
        try:
            a, b = o
        except Exception, e:
            raise Exception("the argument to Command.matchDicts must be a list of duples")

        want[a] = b

    # Walk over the parsed options, and categorize them
    #
    matches = OrderedDict()
    leftovers = OrderedDict()

    for opt, arg in argv.iteritems():
        # If we are looking for the option, match it and convert the argument.
        if opt in want:
            converter = want[opt]
            if converter == None:
                if arg != None:
                    raise Exception("option %s takes no argument" % (CPL.qstr(opt, tquote="'")))
                matches[opt] = None
            else:
                try:
                    convArg = converter(arg)
                except Exception, e:
                    raise Exception("error with option '%s': %s" % (opt, e))

                matches[opt] = convArg

            # Remove the option from the search list.
            del want[opt]

        # If we are not looking for the option, return it as a leftover
        else:
            leftovers[opt] = arg

    return matches, want.keys(), leftovers

