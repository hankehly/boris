import os

import pytest


@pytest.mark.parametrize(
    "tempdir",
    # fmt: off
    [{
        "A": {
            "B": {
                "C.py": "import json"
            }
        },
        "__init__.py": "",
    }],
    # fmt: on
    indirect=True,
)
def test_tempdir(tempdir):
    """Should create a tree of files (with optional content) based on a dict config"""
    files = list(tempdir.rglob("*.py"))
    prefix = len(os.path.commonprefix(files))

    paths_expected = ["A/B/C.py", "__init__.py"]
    paths_actual = sorted(path[prefix:] for path in map(str, files))

    content_expected = "import json"
    content_actual = tempdir.joinpath("A/B/C.py").read_text()

    assert paths_expected == paths_actual
    assert content_expected == content_actual
