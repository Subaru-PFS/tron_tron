__all__ = ['CommError']

import exceptions

class CommError(exceptions.Exception):
    """ An exception that specifies that a low-level communication error occurred. These should only
        be thrown for serious communications errors. The top-level event loop will close/cleanup/destroy
        any running command. The error message will be returned on distxt. 
    """

    def __init__(self, device, error, details=None):
        """ Create a CommError.

        Args:
           device  - name of the device that had an error.
           error   - one line of text, intended for users. Will be returned on distxt.
           details - optional text, intended for operators/programmers. Will be returned on diserrtxt.
       """

        exceptions.Exception.__init__(self)

        self.device = device
        self.error = error
        self.details = details
        if details:
            self.args = (device, error, details)
        else:
            self.args = (device, error)
