import Nubs.mhsActor as mhsActor
reload(mhsActor)

_name = 'mps'

def start(poller, name=None):
    if name == None:
        name = _name
    mhsActor.start(poller, name)

def stop(name=None):
    if name == None:
        name = _name
    mhsActor.stop(name)
