__all__ = ['tback']

import inspect
import pprint
import sys
import traceback

import CPL

def tback(system, e, info=None):
    """ Log a decently informative traceback. """
    
    try:
        frames = inspect.trace()
        toptrace = inspect.trace()[-1]
    except:
        one_liner = "%s: %s: %s" % (e, sys.exc_type, sys.exc_value)
        CPL.error(system, "======== exception botch: %s" % (one_liner))
        return
                
    tr_list = []
    tr_list.append("\n\n====== trace:\n")
    tr_list.append(pprint.pformat(toptrace))

    i = 0
    frames.reverse()
    for f in frames:
        #tr_list.append("\n\n====== frame %d arg+local names:\n" % (i))
        #tr_list.append(pprint.pformat(f[0].f_code.co_varnames))
        tr_list.append("\n\n====== frame %d locals:\n" % (i))
        tr_list.append(pprint.pformat(f[0].f_locals))
        i += 1
        
    ex_list = traceback.format_exception(sys.exc_type, sys.exc_value, sys.exc_traceback)
    CPL.error(system, "\n======== exception: %s\n" % (''.join(ex_list)))
    CPL.error(system, "\n======== exception details: %s\n" % (''.join(tr_list)))

