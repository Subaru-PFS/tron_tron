""" 
"""

class Reply(object):
    """ A complete reply.
    """

    def __init__(self, cid, mid):
        self.cid = cid
        self.mid = mid
        self.lines = []
        self.keys = {}
        
    def appendLine(self, line):
        self.lines.append(line)
        self.keys.update(line.keys)

        
class ReplyLine(object):
    """ A single reply line.
    """

    def __init__(self, src, cid, mid, flag, keys):
        self.src = src
        self.cid = cid
        self.mid = mid
        self.flag = flag
        self.keys = keys

