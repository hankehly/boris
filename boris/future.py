from typing import Any, Optional

import cloudpickle
from pydantic import BaseModel

from .exceptions import InvalidStateError
from .job import Call
from .storage import factory as storage_factory
from .types import CallState, CallStatus


class Future(BaseModel):
    """
    Represents the eventual result of an operation.
    Futures are awaitable objects.

    Interface borrows from concurrent.futures.Future and asyncio.futures.Future

    """

    call: Call

    _state: str = CallState.Pending
    _result: Any = None
    _exception: Exception = None

    class Config:
        arbitrary_types_allowed = True
        underscore_attrs_are_private = True

    @property
    def _storage(self):
        return storage_factory(config=self.call.config)

    def done(self) -> bool:
        """
        Return True if the Future has a result or an exception.
        """
        done_states = [CallState.Success, CallState.Exception]
        return self._state in done_states

    def exception(self) -> Optional[Exception]:
        """
        Return the exception raised by the call.

        Returns
        -------
        Exception (or None)
            The exception (or None if no exception was set) that was set on the Future.

        Raises
        ------
        InvalidStateError
            If the Future is not done yet.

        """
        self._wait()
        if self._state == CallState.Exception:
            return self._exception
        elif not self.done():
            raise InvalidStateError("Future result is not available")
        return None

    def result(self) -> Any:
        """
        Return the result of the Future (the value returned by the call)

        Returns
        -------
        Any
            The result value set by the set_result() method

        Raises
        ------
        Exception
            If the Future has an exception set by the set_exception() method

        InvalidStateError
            If the Future result isn't available yet

        """
        self._wait()
        if self._state == CallState.Success:
            return self._result
        elif self._state == CallState.Exception:
            raise self._exception
        raise InvalidStateError("Future result is not available")

    def _wait(self) -> None:
        """
        Sync the Future with its remote state
        """
        if self.done():
            return
        status = self._get_status_object()
        if status.state == CallState.Success:
            if status.store_function_output:
                result = self._get_result_object()
                self._result = result
            self._state = CallState.Success
        elif status.state == CallState.Exception:
            # Todo: handle exceptions more elegantly
            self._exception = Exception(str(status.error))
            self._state = CallState.Exception

    def _get_status_object(self) -> CallStatus:
        blob = self._storage.get_object(key=self.call.status_key)
        return CallStatus.parse_raw(blob)

    def _get_result_object(self) -> Any:
        blob = self._storage.get_object(key=self.call.result_key)
        return cloudpickle.loads(blob)
