import shutil
import subprocess

from boris import __version__


def test_version():
    """Keep our toml version and __init__ version in sync

    """
    poetry = shutil.which("poetry")

    proc = subprocess.run([poetry, "version"], stdout=subprocess.PIPE)
    toml = proc.stdout.strip().decode().split(" ").pop()

    assert toml == __version__, "pyproject.toml and __version__ out of sync"
