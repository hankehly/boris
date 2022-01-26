import os

import cloudpickle as pickle
import pytest

from boris import Config
from boris.backends.aws.storage import Backend as S3
from boris.future import Future
from boris.job import Call
from boris.types import Backend, CallState, CallStatus, PutObject
from tests.utils import destroy_s3_bucket


class TestFuture:
    """Future class unit tests"""

    @pytest.fixture
    def config(self, moto_server, s3):
        # Todo: This overlaps with a fixture in test_handler.py except for the aws_endpoint_url
        config = Config(
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_endpoint_url=moto_server.docker_external_endpoint_url,
            aws_s3_bucket_name="test",
            aws_s3_bucket_region=os.getenv("AWS_REGION"),
            aws_lambda_region=os.getenv("AWS_REGION"),
            backend=Backend.Aws,
        )
        s3.create_bucket(Bucket=config.aws_s3_bucket_name)
        yield config
        destroy_s3_bucket(s3, name=config.aws_s3_bucket_name)

    def test_success(self, config):
        storage = S3(config=config)

        call = Call(
            id="00001",
            job_id="test_123",
            config=config,
            arg_byte_range=(0, 1),
            store_function_output=True,
        )

        call_status = CallStatus(
            job_id=call.job_id,
            call_id=call.id,
            state=CallState.Success,
            backend=Backend.Aws,
            python_version="test",
            store_function_output=call.store_function_output,
        )

        call_status_blob = call_status.json().encode()
        call_result_blob = pickle.dumps("result of function call")

        storage.put_objects(
            objects=[
                PutObject(body=call_status_blob, key=call.status_key),
                PutObject(body=call_result_blob, key=call.result_key),
            ]
        )

        future = Future(call=call)

        assert not future.done()
        result = future.result()
        assert future.done()
        assert future.exception() is None
        assert result == "result of function call"

    def test_exception(self, config):
        storage = S3(config=config)

        call = Call(
            id="00001",
            job_id="test_123",
            config=config,
            arg_byte_range=(0, 1),
            store_function_output=True,
        )

        call_status = CallStatus(
            job_id=call.job_id,
            call_id=call.id,
            state=CallState.Exception,
            backend=Backend.Aws,
            python_version="test",
            store_function_output=call.store_function_output,
        )

        call_status_blob = call_status.json().encode()
        storage.put_objects(
            objects=[PutObject(body=call_status_blob, key=call.status_key)]
        )

        future = Future(call=call)

        assert not future.done()
        exc = future.exception()
        assert future.done()
        assert isinstance(exc, Exception)
        with pytest.raises(Exception):
            future.result()
