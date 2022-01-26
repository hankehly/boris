class BorisException(Exception):
    pass


class ObjectNotFound(BorisException):
    pass


class NoSuchBucket(BorisException):
    pass


class PutObjectFailed(BorisException):
    pass


class GetObjectFailed(BorisException):
    pass


class MaxAttemptsExceeded(BorisException):
    pass


class InvalidStateError(BorisException):
    pass


class PythonVersionConflict(BorisException):
    def __init__(self, v1, v2):
        self.message = f"Conflicting python runtimes ({v1} != {v2})>"
