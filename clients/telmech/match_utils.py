'''
Match name(s) in a list and return full name
'''

class BadNameMatch(Exception):
    """
    Name not found in match list
    """
    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg

    def __str__(self):
        return self.msg

def match_name(name, names):
    """
    Match this name against list of names and return the full name.

    Arguments:
        name - name to match in names
        names - list of possible names to match against

    Raises an exception if item not found or not unique in list.
    """
    match = []
    exact = []
    for index in range(len(names)):
        item = names[index]
        offset = item.find(name)
        if offset == 0:             # favor strings which match the first chars
            exact.append(item)      # save full name
        elif offset > 0:
            match.append(item)

    # Check for matches at the line beginning.  If none, try inside the string.
    if len(exact) > 0:
        match = exact

    if len(match) == 1:
        return match[0]

    # Should have been just one match.  Fail.
    if len(match) == 0:
        msg = "Item %s not found in %s" % (name, str(names))
    else:
        msg = "Too many parts with %s in %s" % (name, str(names))
    raise BadNameMatch(msg)

def match_names(name_list, names):
    """
    Input list of partial name list and return list of full names
    """
    new_list = map(lambda x: match_name(x.upper(), names), name_list)
    return new_list

def all_names(name_list):
    """
    If 'ALL' is in name_list, return a list of all names less 'ALL'
    """
    new_list = [name for name in name_list]
    if 'ALL' in new_list:
        del new_list[new_list.index('ALL')]   # toss ALL
    
    return new_list
