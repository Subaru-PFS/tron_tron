class cdict:
    """Dictionary, that has case-insensitive keys.
    
    Keys are retained in their original form
    when queried with .keys() or .items().

    Implementation: An internal dictionary maps lowercase
    keys to (key,value) pairs. All key lookups are done
    against the lowercase keys, but all methods that expose
    keys to the user retrieve the original keys.

    Taken from Sami Hangaslammi's ASPN submission:
        http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/66315
    """
    
    def __init__(self, dict=None, dictType=dict):
        """Create an empty dictionary, or update from 'dict'."""
        self._dict = dictType()
        if dict:
            self.update(dict)

    def __contains__(self, key):
        """Case insensitive test where key is in dict"""
        k = key.lower()
        return k in self._dict
  
    def __delitem__(self, key):
        k = key.lower()
        del self._dict[k]

    def __getitem__(self, key):
        """Retrieve the value associated with 'key' (in any case)."""
        k = key.lower()
        return self._dict[k][1]

    def __iter__(self):
        return self.iterkeys()
    
    def __len__(self):
        """Returns the number of (key, value) pairs."""
        return len(self._dict)

    def __repr__(self):
        """String representation of the dictionary."""
        items = ", ".join([("%r: %r" % (k,v)) for k,v in self.items()])
        return "{%s}" % items

    def __setitem__(self, key, value):
        """Associate 'value' with 'key'. If 'key' already exists, but
        in different case, it will be replaced."""
        k = key.lower()
        self._dict[k] = (key, value)

    def __str__(self):
        """String representation of the dictionary."""
        return repr(self)

    def clear(self):
        self._dict.clear()

    def fetch(self, key):
        """ Return both the cased key and the value. """

        k = key.lower()
        return self._dict[k]
        
    def get(self, key, default=None):
        """Retrieve value associated with 'key' or return default value
        if 'key' doesn't exist."""
        try:
            return self[key]
        except KeyError:
            return default

    def setdefault(self, key, default):
        """If 'key' doesn't exists, associate it with the 'default' value.
        Return value associated with 'key'."""
        if not self.has_key(key):
            self[key] = default
        return self[key]

    def has_key(self, key):
        """Case insensitive test wether 'key' exists."""
        k = key.lower()
        return self._dict.has_key(k)

    def items(self):
        """List of (key,value) pairs."""
        return self._dict.values()

    def iteritems(self):
        for key in self.iterkeys():
            yield(key, self[key])
                    
    def iterkeys(self):
        return iter(self.keys())

    def itervalues(self):
        return iter(self.values())

    def keys(self):
        """List of keys in their original case."""
        return [v[0] for v in self._dict.values()]

    def update(self, dict):
        """Copy (key,value) pairs from 'dict'."""
        for k,v in dict.items():
            self[k] = v

    def values(self):
        """List of values."""
        return [v[1] for v in self._dict.values()]

