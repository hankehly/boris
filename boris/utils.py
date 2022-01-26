import base64
import datetime
import itertools
import sys
from typing import Any, List, Tuple

import cloudpickle
from pydantic import BaseModel


class CachedProperty:
    """
    A property that is only computed once per instance and then replaces
    itself with an ordinary attribute. Deleting the attribute resets the
    property.

    Source:
    https://github.com/bottlepy/bottle/commit/fa7733e075da0d790d809aa3d2f53071897e6f76

    """

    def __init__(self, func):
        self.func = func

    def __get__(self, obj, cls):
        if obj is None:
            return self
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value


cached_property = CachedProperty


def bytes_to_ascii(bytes_: bytes) -> str:
    """Encodes a bytes object into a b64 encoded ascii string

    Examples
    --------
    >>> bytes_to_ascii(b"hello world")
    >>> 'aGVsbG8gd29ybGQ='

    """
    return base64.b64encode(bytes_).decode("ascii")


def ascii_to_bytes(ascii_: str) -> bytes:
    """Decodes a b64 encoded ascii string into a bytes object

    Examples
    --------
    >>> ascii_to_bytes('aGVsbG8gd29ybGQ=')
    >>> b'hello world'

    """
    content = ascii_.encode("ascii")
    return base64.b64decode(content)


def timestamp() -> str:
    """An ISO 8601 formatted timestamp with UTC timezone

    Parse with `fromisoformat`

    Examples
    --------
    >>> timestamp()
    >>> '2020-02-11T03:32:39+00:00'

    """
    return datetime.datetime.now(tz=datetime.timezone.utc).isoformat(timespec="seconds")


def python_version(*, sep: str = ".") -> str:
    """Returns the major and minor python version as a string separated by `sep`

    Arguments
    ---------
    sep: str
        The string to stick between the major and minor version

    Examples
    --------
    >>> python_version(sep="")
    >>> "38"

    """
    return sep.join(map(str, (sys.version_info.major, sys.version_info.minor)))


def flatten2d(list_of_lists: List[List]) -> List:
    """Flatten one level of nesting

    Examples
    --------
    >>> flatten2d([["foo"], ["bar"]])
    >>> ["foo", "bar"]

    """
    return list(itertools.chain.from_iterable(list_of_lists))


class ListSerializer(BaseModel):
    """
    Examples
    --------
    >>> serializer = ListSerializer(["foo", 1, {"hello": "world"}])
    >>> serializer.serialize()

    """

    items: List[Any]

    _byte_ranges: List[Tuple[int, int]] = []
    _blob: bytes = None

    class Config:
        underscore_attrs_are_private = True

    @property
    def byte_ranges(self) -> List[Tuple[int, int]]:
        return self._byte_ranges

    @property
    def blob(self) -> bytes:
        return self._blob

    def serialize(self) -> "ListSerializer":
        self._byte_ranges = []
        blobs = []
        pos = 0
        for item in self.items:
            blob = cloudpickle.dumps(item)
            blobs.append(blob)
            blob_size = len(blob)
            self._byte_ranges.append((pos, pos + blob_size))
            pos += blob_size
        self._blob = b"".join(blobs)
        return self
