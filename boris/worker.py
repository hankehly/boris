import abc
from importlib import import_module

from .config import Config
from .job import Job


class Worker(abc.ABC):
    """Interface for all worker backends"""

    @abc.abstractmethod
    def dispatch(self, *, job: Job) -> None:
        pass


def factory(*, config: Config) -> Worker:
    module = import_module(name=f"boris.backends.{config.backend}.worker")
    return getattr(module, "Backend")(config=config)
