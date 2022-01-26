import logging
import math
from typing import List, Tuple

from pydantic import BaseModel, Field

from .config import Config
from .utils import timestamp

logger = logging.getLogger(__name__)


class ArtifactKeyTemplate:
    # fmt: off
    Func       = "jobs/{job_id}/func.pkl"   # noqa
    Bundle     = "jobs/{job_id}/bundle.pkl" # noqa
    Args       = "jobs/{job_id}/args.dat"   # noqa
    CallStatus = "jobs/{job_id}/calls/{call_id}/status.json"
    CallResult = "jobs/{job_id}/calls/{call_id}/result.pkl"
    # fmt: on


class Call(BaseModel):
    """Represents a single invocation"""

    id: str
    job_id: str
    config: Config
    arg_byte_range: Tuple[int, int]
    store_function_output: bool

    @property
    def status_key(self) -> str:
        return ArtifactKeyTemplate.CallStatus.format(
            job_id=self.job_id, call_id=self.id
        )

    @property
    def result_key(self) -> str:
        return ArtifactKeyTemplate.CallResult.format(
            job_id=self.job_id, call_id=self.id
        )

    @property
    def func_key(self) -> str:
        return ArtifactKeyTemplate.Func.format(job_id=self.job_id)

    @property
    def bundle_key(self) -> str:
        return ArtifactKeyTemplate.Bundle.format(job_id=self.job_id)

    @property
    def args_key(self) -> str:
        return ArtifactKeyTemplate.Args.format(job_id=self.job_id)


class Job(BaseModel):
    """Configuration for a single job

    Represents a group of invocations.
    """

    id: str = Field(default_factory=timestamp)
    config: Config
    call_start_pos: int
    call_arg_byte_ranges: List[Tuple[int, int]]
    store_function_output: bool = True
    chunk_size = 100

    @property
    def func_key(self):
        return ArtifactKeyTemplate.Func.format(job_id=self.id)

    @property
    def bundle_key(self):
        return ArtifactKeyTemplate.Bundle.format(job_id=self.id)

    @property
    def args_key(self):
        return ArtifactKeyTemplate.Args.format(job_id=self.id)

    @property
    def n_calls(self):
        return len(self.call_arg_byte_ranges)

    @property
    def n_chunks(self) -> int:
        return math.ceil(self.n_calls / self.chunk_size)

    def chunks(self) -> List["Job"]:
        """Splits a Job into multiple Job instances

        Each new Job has a maximum of chunk_size byte ranges, and the call_start_pos
        is updated to mark the new start location.

        Todo: a ChildJob or SubJob may be more appropriate

        """
        chunks = []
        for i in range(0, self.n_calls, self.chunk_size):
            byte_ranges = self.call_arg_byte_ranges[i : i + self.chunk_size]
            updates = {"call_start_pos": i, "call_arg_byte_ranges": byte_ranges}
            chunk = self.copy(update=updates)
            chunks.append(chunk)
        return chunks

    def calls(self) -> List[Call]:
        """

        """
        calls = []
        for start_pos, i in enumerate(range(self.n_calls), start=self.call_start_pos):
            call = Call(
                id=f"{start_pos:05d}",
                job_id=self.id,
                config=self.config,
                arg_byte_range=self.call_arg_byte_ranges[i],
                store_function_output=self.store_function_output,
            )
            calls.append(call)
        return calls
