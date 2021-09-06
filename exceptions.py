"""Goodwe SEMS exceptions."""


class GoodweException(Exception):
    """Base class for exceptions."""
    def __init__(self, message="Error message not defined"):
        self.message = message
        super().__init__(self.message)

    def __str(self):
        return str(self.message)
        
class TooManyRetries(GoodweException):
    """Too many retries to call API"""
    def __init__(self):
        self.message = "Failed to call GoodWe API (too many retries)"
        super().__init__(self.message)


class FailureWithErrorCode(GoodweException):
    """Too many retries to call API"""
    def __init__(self, code):
        self.message = "Failed to call GoodWe API (return code = {})".format(code)
        super().__init__(self.message)

class FailureWithoutErrorCode(GoodweException):
    """Too many retries to call API"""
    def __init__(self):
        self.message = "Failed to call GoodWe API (no return code )"
        super().__init__(self.message)
