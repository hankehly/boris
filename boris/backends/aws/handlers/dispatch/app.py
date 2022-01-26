import logging
import sys
from concurrent.futures import ThreadPoolExecutor, wait

import botocore.session

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
    """boris dispatch Lambda function

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

        worker_function_name = "BorisWorkerPy" + python_version(sep="")

        logger.info(
            f"received job <"
            f"job id: {job.id}, "
            f"number of tasks: {job.n_calls}, "
            f"worker function name: {worker_function_name}"
            f">"
        )

        with ThreadPoolExecutor() as pool:
            futures = []
            for call in job.calls():
                logger.info(f"Invoking '{worker_function_name}' <call_id: {call.id}>")
                payload = call.json().encode("utf8")
                future = pool.submit(
                    client.invoke,
                    FunctionName=worker_function_name,
                    InvocationType="Event",
                    Payload=payload,
                )
                futures.append(future)
            wait(futures)

        logger.info(f"All {job.n_calls} invocation(s) complete")
        return HandlerFunctionSuccessResponse().dict()
    except Exception:
        exc_info = sys.exc_info()
        exc = ExcInfo.from_sys(exc_info)
        logger.exception("An unhandled exception occurred", exc_info=exc_info)
        return HandlerFunctionErrorResponse(
            errors=[
                Error(
                    status=str(500),
                    code=exc.type,
                    title=exc.value,
                    detail="See meta.traceback for details",
                    meta={"traceback": exc.traceback},
                ),
            ]
        ).dict()
