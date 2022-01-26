import timeit
from importlib import import_module
from textwrap import dedent

import cloudpickle as pickle
import pytest

from boris.bundler import (
    BundleFile,
    Bundler,
    detect_imported_modules,
    find_imports_at_path,
    find_imports_in_module,
    list_dir_contents_of_module,
)


class TestFindImportsAtPath:
    """Unit tests for `find_imports_at_path` function"""

    CONTENT = dedent(
        """
        # top level import statement
        import json

        # top level from ... import statement
        from ast import AST

        try:
            # try-block nested import statements
            import asyncio
            from pickle import dump
        except ImportError:
            pass


        def foo():
            def bar():
                try:
                    import sys
                except ImportError:
                    pass

            pass
        """
    )

    @pytest.mark.parametrize("tempdir", [{"test.py": CONTENT}], indirect=True)
    def test_detect(self, tempdir):
        modules = find_imports_at_path(path=tempdir / "test.py")
        assert modules == ["ast", "asyncio", "json", "pickle", "sys"]

    @pytest.mark.parametrize("tempdir", [{"test.py": ""}], indirect=True)
    def test_empty(self, tempdir):
        modules = find_imports_at_path(path=tempdir / "test.py")
        assert modules == []

    @pytest.mark.parametrize("tempdir", [{"test.py": CONTENT}], indirect=True)
    def test_duration(self, tempdir):
        duration = timeit.timeit(
            lambda: find_imports_at_path(path=tempdir / "test.py"), number=1000
        )
        assert duration <= 1


class TestFindImportsInModule:
    """Unit tests for `find_imports_in_module` function"""

    STRUCT = {
        # fmt: off
        "A": {
            "B": {
                "C": {
                    "__init__.py": "",
                    "c.py": "import subprocess",
                },
                "__init__.py": "",
                "b.py": "import base64",
            },
            "__init__.py": "",
            "a.py": "import json",
        }
        # fmt: on
    }

    @pytest.mark.parametrize(
        "tempdir",
        # fmt: off
        [{
            "__init__.py": "",
            "a.py": "import json"
        }],
        # fmt: on
        indirect=True,
    )
    def test_root_module(self, tempdir, monkeypatch):
        """Should find all import statements in `a.py` given `a` as input"""
        monkeypatch.syspath_prepend(tempdir)
        imports = find_imports_in_module(name="a")
        assert imports == ["json"]

    @pytest.mark.parametrize("tempdir", [STRUCT], indirect=True)
    def test_root_package(self, tempdir, monkeypatch):
        """Should find import statements in files a.py, b.py & c.py given `A` as input"""
        monkeypatch.syspath_prepend(tempdir)
        imports = find_imports_in_module(name="A")
        assert imports == ["base64", "json", "subprocess"]

    @pytest.mark.parametrize("tempdir", [STRUCT], indirect=True)
    def test_submodule(self, tempdir, monkeypatch):
        """Should find import statements in file b.py given `A.B.b` as input"""
        monkeypatch.syspath_prepend(tempdir)
        imports = find_imports_in_module(name="A.B.b")
        assert imports == ["base64"]

    @pytest.mark.parametrize("tempdir", [STRUCT], indirect=True)
    def test_subpackage(self, tempdir, monkeypatch):
        """Should find all import statements in files b.py & c.py given `A.B` as input"""
        monkeypatch.syspath_prepend(tempdir)
        imports = find_imports_in_module(name="A.B")
        assert imports == ["base64", "subprocess"]

    @pytest.mark.parametrize("tempdir", [STRUCT], indirect=True)
    def test_skips_non_source_files(self, tempdir, monkeypatch):
        """Should skip C extensions and pyc files"""
        monkeypatch.syspath_prepend(tempdir)

        (tempdir / "A/x.so").write_text("import ast")
        (tempdir / "A/B/b.pyc").touch()

        imports = find_imports_in_module(name="A")
        assert imports == ["base64", "json", "subprocess"]


class TestListDirContentsOfModule:
    """Unit tests for `list_dir_contents_of_module` function"""

    @pytest.mark.parametrize("tempdir", [{"test123.py": ""}], indirect=True)
    def test_root_module(self, tempdir, monkeypatch):
        """Given a top level module name, returns a 1 item list with absolute file path."""
        monkeypatch.syspath_prepend(tempdir)

        actual = list_dir_contents_of_module(name="test123")
        expected = [str(tempdir / "test123.py")]

        assert actual == expected

    @pytest.mark.parametrize(
        "tempdir",
        # fmt: off
        [{
            "A": {
                "B": {
                    "test.py": ""
                }
            },
            "1.py": "",
            "__init__.py": ""
        }],
        # fmt: on
        indirect=True,
    )
    def test_root_package(self, tempdir, monkeypatch):
        """Given a root package name, we return a recursive list of absolute file paths."""
        # we want to treat the tempdir as a package
        # so we prepend its parent to sys.path
        monkeypatch.syspath_prepend(tempdir.parent)

        actual = list_dir_contents_of_module(name=tempdir.name)

        expected = [
            str(tempdir / "1.py"),
            str(tempdir / "__init__.py"),
            str(tempdir / "A/B/test.py"),
        ]

        assert sorted(actual) == sorted(expected)

    @pytest.mark.parametrize(
        "tempdir",
        # fmt: off
        [{
            "A": {
                "__init__.py": "",
                "a.py": "",
            },
            "__init__.py": "",
        }],
        # fmt: on
        indirect=True,
    )
    def test_submodule(self, tempdir, monkeypatch):
        """
        Submodules are treated the same way as root modules. Given the dotted path to a
        submodule, we return a 1 item list with the absolute path to that submodule.

        """
        monkeypatch.syspath_prepend(tempdir.parent)

        actual = list_dir_contents_of_module(name=f"{tempdir.name}.A.a")
        expected = [str(tempdir.joinpath("A/a.py"))]

        assert actual == expected

    @pytest.mark.parametrize(
        "tempdir",
        # fmt: off
        [{
            "A": {
                "B": {
                    "__init__.py": "",
                    "b.py": "",
                },
                "__init__.py": "",
                "a.py": "",
            },
            "__init__.py": "",
        }],
        # fmt: on
        indirect=True,
    )
    def test_subpackage(self, tempdir, monkeypatch):
        """
        Given a dotted path to a subpackage, should return a recursive list of file
        paths for that package, excluding parent directory files.

        """
        monkeypatch.syspath_prepend(tempdir.parent)

        actual = list_dir_contents_of_module(name=f"{tempdir.name}.A")

        expected = [
            str(tempdir / "A/a.py"),
            str(tempdir / "A/B/b.py"),
            str(tempdir / "A/__init__.py"),
            str(tempdir / "A/B/__init__.py"),
        ]

        assert sorted(actual) == sorted(expected)


class TestDetectImportedModules:
    """Unit tests for `detect_imported_modules` function"""

    @pytest.mark.parametrize(
        "tempdir",
        [
            {
                "A": {
                    "B": {
                        "b.py": dedent(
                            """
                            def f1():
                                pass
                            """
                        ),
                    },
                },
                "C": {
                    "c.py": dedent(
                        """
                        from A.B.b import f1

                        def f2():
                            f1()
                        """
                    ),
                },
            }
        ],
        indirect=True,
    )
    def test_detects_modules_in_function(self, tempdir, monkeypatch):
        """
        Given a function F1 that uses a function from another module F2, we should
        receive the name of the root module for F2 because it is a dependency of F1
        """
        monkeypatch.syspath_prepend(tempdir)
        fn = getattr(import_module("C.c"), "f2")
        result = detect_imported_modules(fn=fn)
        assert result == ["A"]

    @pytest.mark.parametrize(
        "tempdir",
        [
            {
                "A": {
                    "B": {
                        "b.py": dedent(
                            """
                            def f1():
                                pass
                            """
                        ),
                    },
                },
                "C": {
                    "c.py": dedent(
                        """
                        from A.B.b import f1

                        def f2():
                            def f3():
                                a_function()
                        """
                    ),
                },
            }
        ],
        indirect=True,
    )
    def test_detects_modules_in_nested_functions(self, tempdir, monkeypatch):
        """
        When checking imported module dependencies in a function, we should check nested
        functions as well
        """
        monkeypatch.syspath_prepend(tempdir)
        fn = getattr(import_module("C.c"), "f2")
        result = detect_imported_modules(fn=fn)
        assert result == ["A"]

    @pytest.mark.parametrize(
        "tempdir",
        [
            {
                "f.py": dedent(
                    """
                    import math
                    import json as json_renamed

                    def f():
                        math.floor(3.3)
                        json_renamed.loads('[1, 2, 3]')
                    """
                )
            }
        ],
        indirect=True,
    )
    def test_detects_modules(self, tempdir, monkeypatch):
        monkeypatch.syspath_prepend(tempdir)
        fn = getattr(import_module("f"), "f")
        result = detect_imported_modules(fn=fn)
        assert result == ["json", "math"]

    @pytest.mark.parametrize(
        "tempdir",
        # fmt: off
        [
            {
                "A": {
                    "B": {
                        "b.py": "MY_VAR='hello world'"
                    }
                },
                "C": {
                    "c.py": dedent(
                        """
                        from A.B.b import MY_VAR

                        def f1():
                            print(MY_VAR)
                        """
                    ),
                },
            }
        ],
        # fmt: on
        indirect=True,
    )
    def test_ignores_constants(self, tempdir, monkeypatch):
        monkeypatch.syspath_prepend(tempdir)
        fn = getattr(import_module("C.c"), "f1")
        result = detect_imported_modules(fn=fn)
        assert len(result) == 0


class TestBundler:
    """Unit tests for `Bundler` class"""

    STRUCT = {
        "top1": {
            "__init__.py": "",
            "top1.py": dedent(
                """
                def f1():
                    pass
                """
            ),
        },
        "top2": {
            "__init__.py": "",
            "top2.py": dedent(
                """
                from top1.top1 import f1

                def f2():
                    f1()
                """
            ),
        },
    }

    @pytest.mark.parametrize("tempdir", [STRUCT], indirect=True)
    def test_dependencies(self, tempdir, monkeypatch):
        """
        Module dependencies should be available through `dependencies` accessor.
        Names listed in `ignored` should not appear in list.

        """
        monkeypatch.syspath_prepend(tempdir)

        fn = getattr(import_module("top2.top2"), "f2")

        b1 = Bundler(fn=fn)
        b2 = Bundler(fn=fn, ignored=["top1"])

        assert b1.dependencies == ["top1", "top2"]
        assert b2.dependencies == ["top2"]

    @pytest.mark.parametrize("tempdir", [STRUCT], indirect=True)
    def test_package(self, tempdir, monkeypatch):
        """
        Packaging the above mock package should give us a list of BundleFile instances
        serialized as dictionaries. We should have 4 results, each representing of the
        above python files.

        Calling package() should also set `func` to the pickled representation of `fn`

        """
        monkeypatch.syspath_prepend(tempdir)

        fn = getattr(import_module("top2.top2"), "f2")

        bundler = Bundler(fn=fn)
        bundler.package()

        expected = sorted(["__init__.py", "__init__.py", "top1.py", "top2.py"])

        modules = pickle.loads(bundler.bundle)
        actual = sorted([item["path"].name for item in modules])

        assert expected == actual
        assert all(
            isinstance(BundleFile.parse_obj(item), BundleFile) for item in modules
        )

        assert bundler.func == pickle.dumps(fn)

    def test_immutable_properties(self):
        bundler = Bundler(fn=lambda x: x)

        with pytest.raises(AttributeError):
            bundler.bundle = "hello world"

        with pytest.raises(AttributeError):
            bundler.func = "hello world"
