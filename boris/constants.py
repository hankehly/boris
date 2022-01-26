"""
LAMBDA_PY37_RUNTIME_LIBS contains a list of modules importable on lambda python 3.7 runtime.

List was generated from the following sources:
 1. help("modules")
 2. sys.modules
 3. https://github.com/python/cpython/tree/3.7/Lib
"""
# Todo: Need for each runtime (not just py37)
LAMBDA_PY37_RUNTIME_LIBS = {
    "StringIO",
    "__future__",
    "__main__",
    "_abc",
    "_bisect",
    "_blake2",
    "_bootlocale",
    "_codecs",
    "_collections",
    "_collections_abc",
    "_datetime",
    "_dbm",
    "_decimal",
    "_dummy_thread",
    "_elementtree",
    "_frozen_importlib",
    "_frozen_importlib_external",
    "_functools",
    "_gdbm",
    "_hashlib",
    "_heapq",
    "_imp",
    "_io",
    "_json",
    "_locale",
    "_lsprof",
    "_lzma",
    "_markupbase",
    "_md5",
    "_multibytecodec",
    "_multiprocessing",
    "_opcode",
    "_operator",
    "_osx_support",
    "_pickle",
    "_posixsubprocess",
    "_py_abc",
    "_pydecimal",
    "_pyio",
    "_queue",
    "_random",
    "_sha1",
    "_sha256",
    "_sha3",
    "_sha512",
    "_signal",
    "_sitebuiltins",
    "_socket",
    "_sqlite3",
    "_sre",
    "_ssl",
    "_stat",
    "_string",
    "_strptime",
    "_struct",
    "_symtable",
    "_sysconfigdata_m_linux_x86_64-linux-gnu",
    "_testbuffer",
    "_testcapi",
    "_testimportmultiple",
    "_testmultiphase",
    "_thread",
    "_threading_local",
    "_tracemalloc",
    "_warnings",
    "_weakref",
    "_weakrefset",
    "abc",
    "aifc",
    "antigravity",
    "argparse",
    "ast",
    "asynchat",
    "asyncio",
    "asyncore",
    "atexit",
    "base64",
    "bdb",
    "binascii",
    "binhex",
    "bisect",
    "bootstrap",
    "boto3",
    "botocore",
    "builtins",
    "bz2",
    "cProfile",
    "calendar",
    "cgi",
    "cgitb",
    "chunk",
    "cmath",
    "cmd",
    "code",
    "codecs",
    "codeop",
    "collections",
    "collections.abc",
    "colorsys",
    "compileall",
    "concurrent",
    "configparser",
    "contextlib",
    "contextvars",
    "copy",
    "copyreg",
    "crypt",
    "csv",
    "ctypes",
    "curses",
    "dataclasses",
    "datetime",
    "dateutil",
    "dbm",
    "decimal",
    "difflib",
    "dis",
    "distutils",
    "doctest",
    "docutils",
    "dummy_threading",
    "easy_install",
    "email",
    "encodings",
    "ensurepip",
    "enum",
    "errno",
    "faulthandler",
    "fcntl",
    "filecmp",
    "fileinput",
    "fnmatch",
    "formatter",
    "fractions",
    "ftplib",
    "functools",
    "gc",
    "genericpath",
    "getopt",
    "getpass",
    "gettext",
    "glob",
    "grp",
    "gzip",
    "hashlib",
    "heapq",
    "hmac",
    "html",
    "http",
    "http.client",
    "idlelib",
    "imaplib",
    "imghdr",
    "imp",
    "importlib",
    "importlib._bootstrap",
    "importlib._bootstrap_external",
    "importlib.abc",
    "importlib.machinery",
    "importlib.util",
    "inspect",
    "io",
    "ipaddress",
    "itertools",
    "json",
    "json.decoder",
    "json.encoder",
    "json.scanner",
    "keyword",
    "lambda_function",
    "lambda_runtime_client",
    "lambda_runtime_exception",
    "lambda_runtime_marshaller",
    "lib2to3",
    "linecache",
    "locale",
    "logging",
    "lzma",
    "macpath",
    "mailbox",
    "mailcap",
    "marshal",
    "math",
    "mimetypes",
    "mmap",
    "modulefinder",
    "msilib",
    "multiprocessing",
    "netrc",
    "nis",
    "nntplib",
    "ntpath",
    "nturl2path",
    "numbers",
    "opcode",
    "operator",
    "optparse",
    "os",
    "os.path",
    "ossaudiodev",
    "parser",
    "pathlib",
    "pdb",
    "pickle",
    "pickletools",
    "pip",
    "pipes",
    "pkg_resources",
    "pkgutil",
    "platform",
    "plistlib",
    "poplib",
    "posix",
    "posixpath",
    "pprint",
    "profile",
    "pstats",
    "pty",
    "pwd",
    "py_compile",
    "pyclbr",
    "pydoc",
    "pydoc_data",
    "pyexpat",
    "queue",
    "quopri",
    "random",
    "re",
    "readline",
    "reprlib",
    "resource",
    "rlcompleter",
    "runpy",
    "s3transfer",
    "sched",
    "secrets",
    "select",
    "selectors",
    "shelve",
    "shlex",
    "shutil",
    "signal",
    "site",
    "site-packages",
    "smtpd",
    "smtplib",
    "sndhdr",
    "socket",
    "socketserver",
    "sqlite3",
    "sre_compile",
    "sre_constants",
    "sre_parse",
    "ssl",
    "stat",
    "statistics",
    "string",
    "stringprep",
    "struct",
    "subprocess",
    "sunau",
    "symbol",
    "symtable",
    "sys",
    "sysconfig",
    "syslog",
    "tabnanny",
    "tarfile",
    "telnetlib",
    "tempfile",
    "termios",
    "test",
    "test_bootstrap",
    "test_lambda_runtime_client",
    "test_lambda_runtime_marshaller",
    "textwrap",
    "this",
    "threading",
    "time",
    "timeit",
    "tkinter",
    "token",
    "tokenize",
    "trace",
    "traceback",
    "tracemalloc",
    "tty",
    "turtle",
    "turtledemo",
    "types",
    "typing",
    "unicodedata",
    "unittest",
    "urllib",
    "urllib.parse",
    "urllib3",
    "uu",
    "uuid",
    "venv",
    "warnings",
    "wave",
    "weakref",
    "webbrowser",
    "wsgiref",
    "xdrlib",
    "xml",
    "xmlrpc",
    "xxlimited",
    "xxsubtype",
    "zipapp",
    "zipfile",
    "zipimport",
    "zlib",
}

# Todo: determine dynamically
BORIS_INSTALLED_LIBS = {
    "cloudpickle",
    "joblib",
    "psycopg2-binary",
    "pydantic",
    "numpy",
    "pandas",
    "python-dateutil",
    "pytz",
    "six",
    "scikit-learn",
    "sklearn",
    "scipy",
    "threadpoolctl",
}

INSTALLED_LIBS = sorted(LAMBDA_PY37_RUNTIME_LIBS | BORIS_INSTALLED_LIBS)