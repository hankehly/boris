import logging

import botocore.session

from ...config import Config
from ...job import Job
from ...worker import Worker

logger = logging.getLogger(__name__)


class Backend(Worker):
    """AWS Lambda worker"""

    def __init__(self, *, config: Config):
        session = botocore.session.get_session()

        self._client = session.create_client(
            service_name="lambda",
            region_name=config.aws_lambda_region,
            endpoint_url=config.aws_endpoint_url,
            aws_access_key_id=config.aws_access_key_id.get_secret_value(),
            aws_secret_access_key=config.aws_secret_access_key.get_secret_value(),
            aws_session_token=config.aws_session_token.get_secret_value()
            if config.aws_session_token
            else None,
        )

    def dispatch(self, *, job: Job) -> None:
        """Dispatches async job to main lambda handler"""
        function_name = "BorisMainPy" + job.config.python_version.replace(".", "")
        logger.info(f"dispatching job to '{function_name}' handler <job_id: {job.id}>")

        payload = job.copy(
            update={
                "config": job.config.copy(
                    # Todo: handle credentials more systematically
                    exclude={"aws_access_key_id", "aws_secret_access_key"}
                ),
            }
        )

        payload_blob = payload.json().encode()
        self._client.invoke(
            FunctionName=function_name, InvocationType="Event", Payload=payload_blob,
        )
