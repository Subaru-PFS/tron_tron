__all__ = ['tback']

import inspect
import pprint
import sys
import traceback

import CPL

def tback(system, e, info=None):
    """ Log a decently informative traceback. """
    
    try:
        toptrace = inspect.trace()[-1]
    except:
        one_liner = "%s: %s: %s" % (e, sys.exc_type, sys.exc_value)
        CPL.error(system, "======== exception botch: %s" % (one_liner))
        return
                
    tr_list = []
    tr_list.append(pprint.pformat(toptrace))
    tr_list.append(pprint.pformat(toptrace[0].f_locals))
    tr_list.append(pprint.pformat(toptrace[0].f_code.co_varnames))
    
    ex_list = traceback.format_exception(sys.exc_type, sys.exc_value, sys.exc_traceback)
    one_liner = "%s: %s" % (sys.exc_type, sys.exc_value)
    CPL.error(system, "======== exception: %s" % (''.join(ex_list)))
    CPL.error(system, "======== exception (2): %s" % (''.join(tr_list)))

