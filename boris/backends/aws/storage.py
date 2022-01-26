import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, List, Tuple

import botocore.session
from botocore.exceptions import WaiterError
from pydantic import validate_arguments

from ...config import Config
from ...exceptions import (
    GetObjectFailed,
    MaxAttemptsExceeded,
    NoSuchBucket,
    PutObjectFailed,
)
from ...storage import PutObject, Storage

logger = logging.getLogger(__name__)


class Backend(Storage):
    """S3 storage backend"""

    def __init__(self, *, config: Config):
        self.bucket = config.aws_s3_bucket_name

        self._client = botocore.session.get_session().create_client(
            service_name="s3",
            region_name=config.aws_s3_bucket_region,
            endpoint_url=config.aws_endpoint_url,
            aws_access_key_id=config.aws_access_key_id.get_secret_value(),
            aws_secret_access_key=config.aws_secret_access_key.get_secret_value(),
            aws_session_token=config.aws_session_token.get_secret_value()
            if config.aws_session_token
            else None,
        )

    def put_objects(self, *, objects: List[PutObject]) -> None:
        """Uploads 1 or more objects to S3

        As long as this function does not raise an exception, you can expect that it
        succeeded.

        Parameters
        ----------
        objects: List[PutObject]
            A list of objects to upload

        Raises
        ------
        NoSuchBucket
            When the specified bucket does not exist

        PutObjectFailed
            For all other exceptions

        """
        try:
            with ThreadPoolExecutor() as pool:
                fs = []
                for o in objects:
                    future = pool.submit(
                        self._client.put_object,
                        Bucket=self.bucket,
                        Body=o.body,
                        Key=o.key,
                    )
                    fs.append(future)
                # check the result of each future and raise exceptions
                # when present
                for ft in as_completed(fs):
                    ft.result()
        except self._client.exceptions.NoSuchBucket as e:
            raise NoSuchBucket(
                f"The bucket '{e.response['Error']['BucketName']}' does not exist"
            )
        except Exception as e:
            raise PutObjectFailed(str(e))

    @validate_arguments
    def get_object(
        self,
        *,
        key: str,
        max_attempts: int = 20,
        retry_delay: int = 5,
        byte_range: Tuple[int, int] = None,
    ) -> Any:
        """Waits until an object is available and retrieves it from S3

        We poll S3 HeadObject to check if the object exists. If it does, we download it.
        If the object does not become available after max attempts, we raise a not found
        exception.

        Arguments
        ---------
        key: str
            the key of the object to fetch

        max_attempts: int (default 20)
            the max number of times we should retry fetching the object

        retry_delay: int (default 5)
            the delay between retries

        Raises
        ------
        MaxAttemptsExceeded
            when we cannot find the object after `max_attempts`

        GetObjectFailed
            for all other exceptions

        Todo: test get_object failure
        Todo: test byte_range

        """
        logger.debug(
            f"[get_object] <key: {key}, max_attempts: {max_attempts}, delay: {retry_delay}>"
        )

        try:
            waiter = self._client.get_waiter("object_exists")

            waiter.wait(
                Bucket=self.bucket,
                Key=key,
                WaiterConfig={"Delay": retry_delay, "MaxAttempts": max_attempts},
            )

            args = {"Bucket": self.bucket, "Key": key}
            if byte_range:
                args["Range"] = "bytes={0}-{1}".format(*byte_range)

            response = self._client.get_object(**args)
            return response["Body"].read()
        except WaiterError as e:
            raise MaxAttemptsExceeded(str(e))
        except Exception as e:
            raise GetObjectFailed(str(e))
