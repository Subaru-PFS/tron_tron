__all__ = ['ICCError']

import exceptions

class ICCError(exceptions.Exception):
    """ A general exception for the ICC. Anything can throw one, passing a one line error message.
        The top-level event loop will close/cleanup/destroy any running command and return the
        error message on distxt.
    """

    def __init__(self, error, details=None):
        """ Create an ICCError.

        Args:
           error   - one line of text, intended for users. Will be returned on distxt.
           details - optional text, intended for operators/programmers. Will be returned on diserrtxt.
        """
        
        exceptions.Exception.__init__(self)
        
        self.error = error
        self.details = details
        if details:
            self.args = (error, details)
        else:
            self.args = (error,)

