import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, wait

import botocore.session
from pydantic import ValidationError

from boris.exceptions import PythonVersionConflict
from boris.job import Job
from boris.types import (
    Error,
    ExcInfo,
    HandlerFunctionErrorResponse,
    HandlerFunctionSuccessResponse,
)
from boris.utils import python_version

client = botocore.session.get_session().create_client("lambda")
logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    """boris main Lambda function

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
    try:
        job = Job(**event)

        logger.setLevel(job.config.loglevel)
        logger.debug(os.environ)
        logger.debug(event)

        local_python_version = python_version(sep=".")

        logger.info(
            f"received job <"
            f"id: {job.id}, "
            f"call_count: {job.n_calls}, "
            f"python_version: {job.config.python_version}, "
            f"s3_bucket_name: {job.config.aws_s3_bucket_name}, "
            f"s3_bucket_region: {job.config.aws_s3_bucket_region}, "
            f"lambda_python_version: {local_python_version}"
            f">"
        )

        if job.config.python_version != local_python_version:
            raise PythonVersionConflict(
                v1=local_python_version, v2=job.config.python_version
            )

        batch_invoke(job=job)
        logger.info(f"All {job.n_chunks} invocation(s) complete")
        return HandlerFunctionSuccessResponse().dict()
    except ValidationError as e:
        logger.exception(str(e))
        return HandlerFunctionErrorResponse(
            errors=[
                Error(
                    status="400",
                    code="ValidationError",
                    title="Object format validation failed",
                    detail=str(e),
                ),
            ]
        ).dict()
    except PythonVersionConflict as e:
        error = Error(status="400", code="PythonVersionConflict", title=e.message)
        logger.error(e.message)
        return HandlerFunctionErrorResponse(errors=[error]).dict()
    except Exception:
        exc_info = sys.exc_info()
        exc = ExcInfo.from_sys(exc_info)
        logger.exception("An unhandled exception occurred", exc_info=exc_info)
        return HandlerFunctionErrorResponse(
            errors=[
                Error(
                    status="500",
                    code=exc.type,
                    title=exc.value,
                    detail="See meta.traceback for details",
                    meta={"traceback": exc.traceback},
                ),
            ]
        ).dict()


def batch_invoke(*, job: Job) -> None:
    function_name = "BorisDispatchPy" + python_version(sep="")
    with ThreadPoolExecutor() as pool:
        futures = []
        for chunk in job.chunks():
            logger.info(f"Invoking '{function_name}' with {chunk.n_calls} call payload")
            payload = chunk.json().encode("utf8")
            future = pool.submit(
                client.invoke,
                FunctionName=function_name,
                InvocationType="Event",
                Payload=payload,
            )
            futures.append(future)
        wait(futures)
