import traceback
import uuid
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, constr


class LogLevel(str, Enum):
    critical = "CRITICAL"
    error = "ERROR"
    warning = "WARNING"
    info = "INFO"
    debug = "DEBUG"
    notset = "NOTSET"


# Rules for Bucket Naming
# https://docs.aws.amazon.com/AmazonS3/latest/dev/BucketRestrictions.html#bucketnamingrules
S3BucketName = constr(strip_whitespace=True, min_length=3, max_length=63)


class Backend(str, Enum):
    """Backends that boris supports

    Todo: Local, GCP

    """

    Aws = "aws"


class Error(BaseModel):
    """A generic error object

    Properties
    ----------
    id: str
        a unique identifier for this particular occurrence of the problem

    status: str
        the HTTP status code applicable to this problem, expressed as a string value

    title: str
        a short, human-readable summary of the problem

    code: str
        an application-specific error code, expressed as a string value

    detail: str
        a human-readable explanation specific to this occurrence of the problem

    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: str = None
    title: str = None
    code: str = None
    detail: str = None
    meta: dict = None


class ExcInfo(BaseModel):
    """Models an exception with name, value and traceback information

    Todo: from_exc(Exception) so we don't have to import sys
    """

    type: str
    value: str
    traceback: str

    @classmethod
    def from_sys(cls, exc_info: tuple):
        type_, value, _ = exc_info

        return cls(
            type=type_.__name__,
            value=str(value),
            traceback=str(traceback.format_exception(*exc_info)),
        )


class CallState(str, Enum):
    Exception = "exception"
    Success = "success"
    Pending = "pending"


class CallStatus(BaseModel):
    job_id: str
    call_id: str
    state: CallState
    error: Optional[Error] = None
    backend: str
    store_function_output: bool
    python_version: str
    metrics: dict = {}

    class Config:
        use_enum_values = True


class PutObject(BaseModel):
    body: bytes
    key: constr(strip_whitespace=True, min_length=1)


class HandlerFunctionSuccessResponse(BaseModel):
    data: Union[List, Dict] = None
    meta: Dict = {}


class HandlerFunctionErrorResponse(BaseModel):
    errors: List[Error] = []
    meta: Dict = {}
