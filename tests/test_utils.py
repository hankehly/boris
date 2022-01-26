import datetime
import sys

from hypothesis import given
from hypothesis import strategies as st

from boris.utils import (
    ascii_to_bytes,
    bytes_to_ascii,
    flatten2d,
    python_version,
    timestamp,
)


@given(st.binary())
def test_ascii_encode_decode(b):
    assert b == ascii_to_bytes(bytes_to_ascii(b))


def test_timestamp():
    """Check that the timestamp we generate is a valid datetime

    If we ever drop support for 3.6, change this to:
    assert datetime.datetime.fromisoformat(timestamp()).tzinfo == datetime.timezone.utc

    """
    ts = timestamp()
    assert datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S+00:00")


def test_python_version():
    major = sys.version_info.major
    minor = sys.version_info.minor
    assert python_version() == f"{major}.{minor}"
    assert python_version(sep="") == f"{major}{minor}"


def test_flatten2d():
    dim2 = [["foo"], ["bar"]]
    assert flatten2d(dim2) == ["foo", "bar"]

    dim3 = [["foo"], ["bar", ["baz"]]]
    assert flatten2d(dim3) == ["foo", "bar", ["baz"]]
