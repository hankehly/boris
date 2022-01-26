import logging
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Union

import cloudpickle as pickle
from pydantic import SecretStr

from boris.job import Call
from boris.storage import PutObject
from boris.storage import factory as storage_factory
from boris.types import (
    Backend,
    CallState,
    CallStatus,
    Error,
    ExcInfo,
    HandlerFunctionErrorResponse,
    HandlerFunctionSuccessResponse,
)
from boris.utils import ascii_to_bytes, python_version

logger = logging.getLogger(__name__)

TEMP_PATH = Path("/tmp")
BUNDLE_PATH = Path(TEMP_PATH / "__boris__")


def lambda_handler(event, context):
    """boris worker Lambda function

    Parameters
    ----------
    event: dict, required
        The event payload should be a serialized Job instance
        https://docs.aws.amazon.com/lambda/latest/dg//python-programming-model-handler-types.html

    context: object, required
        Lambda Context runtime methods and attributes
        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    -------
    Union[HandlerFunctionSuccessResponse, HandlerFunctionErrorResponse]
        either a success or error response object

    """
    call = Call(**event)
    logger.setLevel(call.config.loglevel)

    logger.info(
        f"received call <"
        f"id: {call.id}, "
        f"job_id: {call.job_id}, "
        f"bucket: {call.config.aws_s3_bucket_name}, "
        f"bucket region: {call.config.aws_s3_bucket_region}"
        f">"
    )

    config = call.config.copy(
        update={
            "aws_access_key_id": SecretStr(os.getenv("AWS_ACCESS_KEY_ID")),
            "aws_secret_access_key": SecretStr(os.getenv("AWS_SECRET_ACCESS_KEY")),
            "aws_session_token": SecretStr(os.getenv("AWS_SESSION_TOKEN")),
        }
    )

    storage = storage_factory(config=config)
    local_python_version = python_version(sep=".")

    try:
        func_blob = storage.get_object(key=call.func_key)
        bundle_blob = storage.get_object(key=call.bundle_key)
        arg_blob = storage.get_object(key=call.args_key, byte_range=call.arg_byte_range)

        bundle_path = recreate_directory_at(path=BUNDLE_PATH)
        sys.path.insert(0, str(bundle_path))

        unpack_start = time.time()
        for module in pickle.loads(bundle_blob):
            blob = ascii_to_bytes(module["repr_base64"])
            path = str(module["path"])
            root = path.index(module["root"])
            dest = bundle_path / path[root:]

            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)

            logger.debug(
                f"wrote module to disk "
                f"<root: {module['root']}, size: {module['size']}, dest: {dest}>"
            )

        unpack_stop = time.time()
        unpack_duration = round(unpack_stop - unpack_start, 2)

        logger.debug(
            f"finished unpacking modules to local filesystem "
            f"<duration: {unpack_duration}>"
        )

        # Load function and arguments into memory AFTER unpacking bundle to local
        # filesystem to prevent module-does-not-exist errors
        func = pickle.loads(func_blob)
        arg_data = pickle.loads(arg_blob)

        exec_start = time.time()
        result = func(arg_data)
        exec_stop = time.time()
        exec_duration = round(exec_stop - exec_start, 2)

        logger.debug(f"function execution complete <duration: {exec_duration}>")

        remaining_time_in_millis = context.get_remaining_time_in_millis()
        disk_usage = shutil.disk_usage(TEMP_PATH)

        call_status = CallStatus(
            job_id=call.job_id,
            call_id=call.id,
            state=CallState.Success,
            backend=Backend.Aws,
            python_version=local_python_version,
            store_function_output=call.store_function_output,
            metrics={
                "unpack_duration": unpack_duration,
                "exec_duration": exec_duration,
                "disk_usage_total": disk_usage.total,
                "disk_usage_used": disk_usage.used,
                "disk_usage_free": disk_usage.free,
                "memory_limit_in_mb": context.memory_limit_in_mb,
                "remaining_time_in_millis": remaining_time_in_millis,
            },
        )

        call_status_blob = call_status.json().encode()
        store_objects = [PutObject(body=call_status_blob, key=call.status_key)]

        if call.store_function_output:
            call_result_blob = pickle.dumps(result)
            store_objects.append(PutObject(body=call_result_blob, key=call.result_key))

        storage.put_objects(objects=store_objects)
        return HandlerFunctionSuccessResponse().dict()
    except Exception:  # noqa
        exc = sys.exc_info()
        exc_info = ExcInfo.from_sys(exc)

        logger.exception("An unhandled exception occurred", exc_info=exc_info)

        error = Error(
            status="500",
            title=exc_info.value,
            code=exc_info.type,
            detail="See meta.traceback for details",
            meta={"traceback": exc_info.traceback},
        )

        remaining_time_in_millis = context.get_remaining_time_in_millis()
        disk_usage = shutil.disk_usage(TEMP_PATH)

        call_status = CallStatus(
            job_id=call.job_id,
            call_id=call.id,
            state=CallState.Exception,
            error=error,
            backend=Backend.Aws,
            python_version=local_python_version,
            store_function_output=call.store_function_output,
            metrics={
                "disk_usage_total": disk_usage.total,
                "disk_usage_used": disk_usage.used,
                "disk_usage_free": disk_usage.free,
                "memory_limit_in_mb": context.memory_limit_in_mb,
                "remaining_time_in_millis": remaining_time_in_millis,
            },
        )

        call_status_blob = call_status.json().encode()
        storage.put_objects(
            objects=[PutObject(body=call_status_blob, key=call.status_key)]
        )
        return HandlerFunctionErrorResponse(errors=[error]).dict()


def recreate_directory_at(*, path: Union[str, Path]) -> Path:
    """
    Destroys (if anything exists) and recreates path as a directory.

    Notes
    -----
    Lambda may reuse function instances to serve subsequent requests rather than
    creating a new copy. To prevent disk-usage errors and mixed bundles, delete
    and reuse the same temporary directory on each invocation.

    """
    path = Path(path)
    if path.exists():
        logger.debug("directory already exist. deleting")
        shutil.rmtree(path)
        path.mkdir()
    return path
