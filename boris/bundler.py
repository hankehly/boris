import ast
import inspect
import logging
from importlib.machinery import (
    BYTECODE_SUFFIXES,
    EXTENSION_SUFFIXES,
    SOURCE_SUFFIXES,
    BuiltinImporter,
    ModuleSpec,
)
from importlib.util import find_spec
from pathlib import Path
from pkgutil import iter_modules
from typing import Iterable, List, Optional, Set

import cloudpickle as pickle
from pydantic import BaseModel, ByteSize, FilePath, constr, validator

from .utils import bytes_to_ascii, cached_property

logger = logging.getLogger(__name__)


def _iterable_node(*, node: ast.AST) -> bool:
    return hasattr(node, "body") and isinstance(node.body, Iterable)


def _absolute_import_from(*, node: ast.AST) -> bool:
    return isinstance(node, ast.ImportFrom) and node.level == 0


def find_absolute_import_statements_in_node(*, node: ast.AST) -> Set[str]:
    """Recursively detects all absolute import statements in AST node

    1. import statements or `from ...` import statements at top level

        import alib
        from alib import amodule

    2. import statements nested inside try-except blocks or functions

        def foo():
            def bar():
                try:
                    import alib
                except ImportError:
                    pass

    For submodule import statements (ie `import importlib.util`) we return the
    top level module name.

    We do not return relative import statements like the following:
        from ..foo.bar import a as b, c

    Parameters
    ----------
    node
        the AST node to search

    Returns
    -------
    Set[str]
        A set of importable package names (ie `numpy`)
        In the case of an empty file, an empty set.

    Examples
    --------
    >>> find_absolute_import_statements_in_node(node=node)
    ["importlib", "logging", "pkgutil", "typing"]

    """
    if isinstance(node, ast.Import):
        return set(map(lambda alias: alias.name.split(".")[0], node.names))
    elif _absolute_import_from(node=node):
        return {node.module.split(".")[0]}
    elif _iterable_node(node=node):
        found = set()
        for child in ast.iter_child_nodes(node):
            imported = find_absolute_import_statements_in_node(node=child)
            found.update(imported)
        return found
    return set()


def find_imports_at_path(*, path: str) -> List[str]:
    """
    Wrapper around `find_imports_at_node` that takes a path string as an argument.
    Internally converts `path` to AST node and calls `find_imports_at_node`

    Parameters
    ----------
    path
        the path to the file to parse

    Returns
    -------
    List[str]
        A sorted unique list of importable package names (ie `numpy`)
        In the case of an empty file, an empty set.

    Examples
    --------
    >>> find_imports_at_path(path="/path/to/file.py")
    ["importlib", "logging", "pkgutil", "typing"]

    """
    logger.debug(f"find_imports_at_path(path='{path}')")
    body = Path(path).read_bytes()
    node = ast.parse(body)
    found = find_absolute_import_statements_in_node(node=node)
    return sorted(found)


def find_imports_in_module(*, name: str) -> List[str]:
    """
    Takes a module or package name (eg `pandas`) and returns a list of imported module
    names for that module or package.

    If `name` points to a package, we recursively check all files in that package.

    TODO: `find_spec` imports parent modules when `name` includes a dot (`.`)
          this behavior may cause inspection to fail even though we do not
          care about importing anything

    Parameters
    ----------
    name: str
        a module or package name to inspect (must be importable)

    Returns
    -------
    List[str]
        a sorted list of module names

    Notes
    -----
    This function only inspects python source files (ie files ending in `.py`).
    Other file types, like C extensions and pyc files are ignored.

    """
    logger.debug(f"find_imports_in_module(name='{name}')")

    def find_imports_for_spec(*, spec: ModuleSpec):
        if spec.loader.is_package(spec.name):
            found = set()
            for info, module_name, _ in iter_modules(spec.submodule_search_locations):
                submodule = info.find_spec(module_name)
                modules = find_imports_for_spec(spec=submodule)
                found.update(modules)
            return found
        is_source_file = Path(spec.origin).suffix in SOURCE_SUFFIXES
        if is_source_file:
            return find_imports_at_path(path=spec.origin)
        return set()

    root_spec = find_spec(name)
    imports = find_imports_for_spec(spec=root_spec)
    return sorted(imports)


def list_dir_contents_of_module(*, name: str) -> List[str]:
    """
    If name is a package, returns a recursive list of absolute paths to every python
    file in that package.

    If name is a filename, returns a 1 items list with the absolute path to that file.

    Returns an empty list if name does not correspond to a package or a filename.

    Parameters
    ----------
    name: str
        A package or python module name (eg. pandas)

    Returns
    -------
    List[str]
        A recursive list of absolute file paths.

    """
    logger.debug(f"list_dir_contents_of_module(name='{name}')")
    spec = find_spec(name)

    if spec is None:
        logger.debug(f"spec not found for '{name}'")
        return []

    paths = []
    if spec.loader.is_package(spec.name):
        logger.debug(
            f"{spec.name} is a package "
            f"<len(search locations)={len(spec.submodule_search_locations)}>"
        )
        for directory in spec.submodule_search_locations:
            paths.extend(_glob(directory))

    # builtins have no `origin` and should be available without packaging
    elif spec.loader != BuiltinImporter:
        paths.append(spec.origin)

    return paths


def _glob(directory: str):
    """Recursively lists all files in `directory`

    Parameters
    ----------
    directory: str
        list all the paths (excluding blacklist items) in this directory

    Notes
    -----
    Filter paths with a blacklist instead of whitelist, because blindly excluding
    unknown file types may cause runtime bugs that are difficult to trace.

    For example, the requests library depenends on .pem files.

    One downside to this is that the bundle size may increase; but this seems like a
    fair trade-off for not having to maintain a list of file types that *might* be
    needed.
    """
    logger.debug(f"_glob(directory='{directory}')")
    blacklist = BYTECODE_SUFFIXES + EXTENSION_SUFFIXES

    paths = []
    for path in Path(directory).rglob("*"):
        if path.is_file() and path.suffix not in blacklist:
            paths.append(str(path))

    return paths


def detect_globalvars(func):  # noqa
    """
    non-recursive

    Source:
    https://github.com/uqfoundation/dill/blob/master/dill/detect.py
    """
    if inspect.ismethod(func):
        func = getattr(func, "__func__")
    if inspect.isfunction(func):
        globs = {}
        orig_func, func = func, set()
        for obj in getattr(orig_func, "__closure__") or {}:
            _vars = detect_globalvars(obj.cell_contents) or {}
            func.update(_vars)
            globs.update(_vars)
        globs.update(getattr(orig_func, "__globals__") or {})
        func.update(getattr(orig_func, "__code__").co_names)
    else:
        return {}
    return dict((name, globs[name]) for name in func if name in globs)


def detect_imported_modules(*, fn) -> List[str]:
    """
    Finds the root level names of global modules referred to from within `fn`
    It does not pick up global variables

    TODO: (possible bug) Make sure functions with decorators are handled correctly
    TODO: Handle objects other than functions like methods and classes with __call__
    TODO: Add test to check that we catch "isclass"

    Parameters
    ----------
    fn: python function
        a python function

    Returns
    -------
    List[str]
        a sorted list of module or function names

    Examples
    --------
    >>> #### alib.py ####
    >>> GLOBAL_VAR=1
    >>>
    >>> def global_function():
    >>>     pass
    >>>
    >>> #### some other file ####
    >>> from alib import GLOBAL_VAR, global_function  # noqa
    >>> import pandas as pd  # noqa
    >>>
    >>> def fn():
    >>>     print(GLOBAL_VAR)
    >>>     print(global_function())
    >>>     print(pd.Series([1, 2, 3]))
    >>>
    >>> detect_imported_modules(fn=fn)
    ["alib", "pandas"]

    """
    found = set()
    for var in detect_globalvars(fn).values():
        if inspect.isfunction(var) or inspect.isclass(var):
            name = var.__module__.split(".")[0]
            logger.debug(f"found globalvar <name: '{name}', type: function>")
            found.add(name)
        elif inspect.ismodule(var):
            name = var.__name__.split(".")[0]
            logger.debug(f"found globalvar <name: '{name}', type: module>")
            found.add(name)
        else:
            logger.warning(
                f"globalvar is not a function, class or module <var: {var}, type: {type(var)}>"
            )
    return sorted(found)


class BundleFile(BaseModel):
    """A utility class for modeling a file that we bundle.

    During BundleFile instance construction we make sure the file exists and serialize
    a base64 ascii representation of the contents.

    Properties
    ----------
    path: str
        a path pointing to the module file on the local machine

    root: str
        the component in `path` to use as root (must be a substring of `path`)

    size: int
        the size of the module file
        this attribute is set dynamically on initialization

    repr_base64: str
        an ascii encoded base64 representation of the module file
        this attribute is set dynamically on initialization

    TODO: If you pass a dummy path, the FilePath validation should occur first

    """

    path: FilePath
    root: constr(strip_whitespace=True, strict=True, min_length=1)
    size: ByteSize = None
    repr_base64: str = None

    class Config:
        allow_mutation = False

    @validator("root")
    def check_root_in_path(cls, v, *, values, config, field):
        """
        `root` must be a substring of `path`
        """
        if v not in str(values["path"]):
            raise ValueError(f"{v} not found in path")
        return v

    @validator("size", always=True)
    def set_size(cls, v, *, values, config, field):
        return Path(values["path"]).stat().st_size

    @validator("repr_base64", always=True)
    def set_repr_base64(cls, v, *, values, config, field):
        return bytes_to_ascii(Path(values["path"]).read_bytes())


class Bundler:
    """
    Takes a function as input, searches for and packages all module dependencies as a
    list of `BundleFile` instances.

    Properties
    ----------
    bundle: bytes (List[BundleFile])
        a pickled list of BundleFile instances serialized as dictionaries. It
        represents the python modules and other files required by the input function.
        this value is null until the `package` method is called

    func: bytes (Callable)
        the pickled function

    dependencies: List[str]
        a list of module names and packages that the input function relies on
        excluding `ignored`

    Parameters
    ----------
    fn: python function
        the python function to package

    ignored: List[str] (defaults to an empty list)
        a list of module or package names to ignore when packaging the function

    Examples
    --------
    >>> bundler = Bundler(fn=a_function)
    >>> bundler.package()
    >>> bundler.bundle
    b'...'

    TODO: Test that we raise ValueError when function module is __main__

    """

    def __init__(self, *, fn, ignored: Optional[List[str]] = None):
        self.__fn = fn
        self.__ignored = [] if ignored is None else ignored
        self.__bundle: Optional[bytes] = None
        self.__func: Optional[bytes] = None

    @property
    def bundle(self) -> Optional[bytes]:
        return self.__bundle

    @property
    def func(self) -> Optional[bytes]:
        return self.__func

    @cached_property
    def dependencies(self) -> List[str]:
        """
        A recursive sorted list of module and package names that the input function
        depends on.

        Names listed in `ignored` are filtered out.

        """
        names = set()

        modules = detect_imported_modules(fn=self.__fn)
        modules.append(self.__fn.__module__.split(".")[0])

        # remove things we know we don't need
        modules = set(modules) - {"__main__"}
        modules = set(modules) - set(self.__ignored)

        for name in modules:
            found = find_imports_in_module(name=name)
            names.add(name)
            names.update(found)

        filtered = names - set(self.__ignored)
        return sorted(filtered)

    def package(self):
        bundle = []

        for name in self.dependencies:
            paths = list_dir_contents_of_module(name=name)

            for path in paths:
                logger.debug(f"adding module to package <path: {path}>")
                file = BundleFile(path=path, root=name).dict()
                bundle.append(file)

        logger.debug("gathered all modules, begin pickling")
        self.__bundle = pickle.dumps(bundle)
        self.__func = pickle.dumps(self.__fn)
