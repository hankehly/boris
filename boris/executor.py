import logging
import time
from typing import List, Tuple

from pydantic import BaseModel

from .bundler import Bundler
from .config import Config
from .constants import INSTALLED_LIBS
from .future import Future
from .job import Job
from .storage import PutObject, Storage
from .storage import factory as storage_factory
from .utils import ListSerializer
from .worker import Worker
from .worker import factory as worker_factory

logger = logging.getLogger(__name__)


class Executor(BaseModel):
    """Entrypoint for function execution

    TODO: allow user to add `ignored` modules

    # executor = boris.Executor(config=Config)
    # executor.map(train_model, [foo, bar, foo, bar], store_function_output=False)

    """

    config: Config

    @property
    def _storage(self) -> Storage:
        return storage_factory(config=self.config)

    @property
    def _worker(self) -> Worker:
        return worker_factory(config=self.config)

    def _serialize_args(self, *args) -> Tuple[bytes, List[Tuple[int, int]]]:
        serializer = ListSerializer(items=list(args)).serialize()
        return serializer.blob, serializer.byte_ranges

    def map(self, fn, *args, store_function_output=True) -> List[Future]:
        """
        Serializes input function and dependencies, uploads to storage, starts worker
        invocation and returns list of Future objects.

        """
        args_blob, byte_ranges = self._serialize_args(*args)

        job = Job(
            config=self.config,
            store_function_output=store_function_output,
            call_start_pos=0,
            call_arg_byte_ranges=byte_ranges,
        )

        logger.debug(f"bundling modules <job: {str(job.id)}>")

        bundle_start = time.time()
        bundler = Bundler(fn=fn, ignored=INSTALLED_LIBS)
        bundler.package()
        bundle_stop = time.time()
        bundle_duration = round(bundle_stop - bundle_start, 2)

        logger.debug(
            f"bundle packaging complete "
            f"<job: {str(job.id)}, duration: {bundle_duration}>"
        )

        logger.debug(f"uploading bundled data <job: {str(job.id)}>")
        upload_start = time.time()

        self._storage.put_objects(
            objects=[
                PutObject(body=bundler.func, key=job.func_key),
                PutObject(body=bundler.bundle, key=job.bundle_key),
                PutObject(body=args_blob, key=job.args_key),
            ]
        )

        upload_stop = time.time()
        upload_duration = round(upload_stop - upload_start, 2)

        logger.debug(
            f"bundled data upload complete "
            f"<job: {str(job.id)}, duration: {upload_duration}>"
        )

        logger.debug(f"start function invocation <job: {str(job.id)}>")
        self._worker.dispatch(job=job)

        futures = [Future(call=call) for call in job.calls()]
        return futures
