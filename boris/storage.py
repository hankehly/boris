import abc
from importlib import import_module
from typing import Any, List, Tuple

from .config import Config
from .types import PutObject


class Storage(abc.ABC):
    """Interface for all storage backends"""

    @abc.abstractmethod
    def put_objects(self, *, objects: List[PutObject]) -> None:
        pass

    @abc.abstractmethod
    def get_object(
        self,
        *,
        key: str,
        max_attempts: int = 20,
        delay: int = 5,
        byte_range: Tuple[int, int] = None,
    ) -> Any:
        pass


def factory(*, config: Config) -> Storage:
    module = import_module(name=f"boris.backends.{config.backend}.storage")
    return getattr(module, "Backend")(config=config)
