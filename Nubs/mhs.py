import Nubs.mhsActor as mhsActor
reload(mhsActor)

def start(poller, name=None):
    if name == None:
        raise RuntimeError("actor name is not defined in start()")
    mhsActor.start(poller, name)

def stop(name=None):
    if name == None:
        raise RuntimeError("actor name is not defined in stop()")
    mhsActor.stop(name)
