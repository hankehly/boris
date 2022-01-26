import json
import os
from importlib import import_module
from textwrap import dedent
from unittest.mock import call, patch

import cloudpickle as pickle
import pytest

from boris.bundler import Bundler
from boris.config import Config
from boris.job import Job
from boris.types import (
    Backend,
    CallState,
    CallStatus,
    HandlerFunctionErrorResponse,
    HandlerFunctionSuccessResponse,
)
from boris.utils import ListSerializer
from tests.utils import destroy_s3_bucket


@pytest.fixture(scope="function")
def boris_config(moto_server, s3):
    """
    Notes
    -----
    aws_endpoint_url is set to the moto-server docker-instance internal url
    so this fixture is meant for clients running api calls inside of the docker network

    """
    config = Config(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        aws_endpoint_url=moto_server.docker_internal_endpoint_url,
        aws_s3_bucket_name="test",
        aws_s3_bucket_region=os.getenv("AWS_REGION"),
        aws_lambda_region=os.getenv("AWS_REGION"),
        backend=Backend.Aws,
    )

    s3.create_bucket(Bucket=config.aws_s3_bucket_name)
    yield config
    destroy_s3_bucket(s3, name=config.aws_s3_bucket_name)


class TestBorisMainHandler:
    """Unit tests for BorisMainPy3x lambda function handler"""

    def test_ok(self, boris_config, s3, moto_server, aws_dispatch_function_identifier):
        """Check that the main handler invokes dispatch function with correct arguments

        For this test, we send the handler 3 tasks with a chunk size to 2. This means
        we should see 2 calls from botocore to the dispatch function.

        """
        from boris.backends.aws.handlers.main.app import lambda_handler

        serializer = ListSerializer(items=[None for _ in range(1, 4)]).serialize()

        job = Job(
            config=boris_config.copy(
                update={"aws_endpoint_url": moto_server.docker_external_endpoint_url}
            ),
            chunk_size=2,
            call_start_pos=0,
            call_arg_byte_ranges=serializer.byte_ranges,
        )

        expected_calls = [
            call(
                FunctionName=aws_dispatch_function_identifier,
                InvocationType="Event",
                Payload=chunk.json().encode("utf8"),
            )
            for chunk in job.chunks()
        ]

        s3.put_object(
            Bucket=boris_config.aws_s3_bucket_name,
            Body=serializer.blob,
            Key=job.args_key,
        )

        with patch("boris.backends.aws.handlers.main.app.client.invoke") as client:
            payload = job.copy(
                update={
                    "config": job.config.copy(
                        update={
                            "aws_endpoint_url": moto_server.docker_external_endpoint_url
                        }
                    ),
                }
            )
            event = payload.dict()
            response = lambda_handler(event, None)
            assert HandlerFunctionSuccessResponse(**response)
            client.assert_has_calls(expected_calls)

    def test_invalid_job(self, sam_local_invoke, aws_main_function_identifier):
        """An invalid job configuration should raise an exception"""
        response = sam_local_invoke(
            function_identifier=aws_main_function_identifier,
            event={"invalid": ["payload", "format"]},
        )

        assert isinstance(response, HandlerFunctionErrorResponse)
        assert len(response.errors) == 1
        err = response.errors[0]
        assert err.code == "ValidationError"
        assert err.status == "400"
        assert err.title == "Object format validation failed"

    def test_runtime_conflict(self, sam_local_invoke, aws_main_function_identifier):
        job = Job(
            config=Config(
                backend=Backend.Aws,
                python_version="2.7",
                aws_s3_bucket_name="test",
                aws_s3_bucket_region="us-east-1",
                aws_lambda_region="us-east-1",
            ),
            call_start_pos=0,
            call_arg_byte_ranges=[(0, 1)],
        )

        event = json.loads(job.json())
        response = sam_local_invoke(
            function_identifier=aws_main_function_identifier, event=event
        )

        assert isinstance(response, HandlerFunctionErrorResponse)
        assert len(response.errors) == 1

        err = response.errors[0]
        assert err.code == "PythonVersionConflict"
        assert err.status == "400"


class TestBorisDispatchHandler:
    """Unit tests for BorisDispatchPy3x lambda function handler"""

    def test_ok(self, aws_worker_function_identifier):
        """
        Given
        -----
        The dispatch handler receives a Job with 3 calls.

        Expectation
        -----------
        The dispatch handler triggers the worker handler 3 times. Each invocation payload
        contains the contents of one of the calls.

        """
        from boris.backends.aws.handlers.dispatch.app import lambda_handler

        job = Job(
            config=Config(
                backend=Backend.Aws,
                aws_s3_bucket_name="test",
                aws_s3_bucket_region="us-east-1",
                aws_lambda_region="us-east-1",
            ),
            call_start_pos=0,
            call_arg_byte_ranges=[(0, 1), (1, 2), (2, 3)],
        )

        expected_calls = [
            call(
                FunctionName=aws_worker_function_identifier,
                InvocationType="Event",
                Payload=call_.json().encode("utf8"),
            )
            for call_ in job.calls()
        ]

        with patch("boris.backends.aws.handlers.dispatch.app.client.invoke") as client:
            response = lambda_handler(json.loads(job.json()), None)
            assert HandlerFunctionSuccessResponse(**response)
            client.assert_has_calls(expected_calls)

    def test_err(self):
        """Any sort of exception should result in a HandlerFunctionErrorResponse"""
        from boris.backends.aws.handlers.dispatch.app import lambda_handler

        response = lambda_handler({"invalid": "payload"}, None)
        response = HandlerFunctionErrorResponse(**response)
        assert len(response.errors) == 1
        assert response.errors[0].status == "500"
        assert response.errors[0].code == "ValidationError"


class TestBorisWorkerHandler:
    """Unit tests for BorisWorkerPy3x lambda function handler

    See if something like this could help you speed up tests
    https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-using-automated-tests.html

    """

    @pytest.mark.parametrize(
        "tempdir",
        [
            {
                "ok.py": dedent(
                    """
                    from dependency import add

                    def func(payload):
                        return add(payload['x'], payload['y'])
                    """
                ),
                "dependency.py": dedent(
                    """
                    def add(x: int, y: int) -> int:
                        return x + y
                    """
                ),
            }
        ],
        indirect=True,
    )
    def test_ok_store_function_output(
        self,
        tempdir,
        monkeypatch,
        s3,
        boris_config,
        sam_local_invoke,
        aws_worker_function_identifier,
    ):
        """Checks for expected function output and status objects in storage

        Given
        -----

        Expectation
        -----------

        """
        monkeypatch.syspath_prepend(tempdir)
        func = getattr(import_module("ok"), "func")

        bundler = Bundler(fn=func)
        bundler.package()

        serializer = ListSerializer(
            items=[{"x": 1, "y": 2}, {"x": 3, "y": 4}]
        ).serialize()

        job = Job(
            config=boris_config,
            call_start_pos=0,
            call_arg_byte_ranges=serializer.byte_ranges,
        )

        s3.put_object(
            Bucket=boris_config.aws_s3_bucket_name, Body=bundler.func, Key=job.func_key,
        )

        s3.put_object(
            Bucket=boris_config.aws_s3_bucket_name,
            Body=bundler.bundle,
            Key=job.bundle_key,
        )

        s3.put_object(
            Bucket=boris_config.aws_s3_bucket_name,
            Body=serializer.blob,
            Key=job.args_key,
        )

        calls = job.calls()

        # Check first call
        event = json.loads(calls[0].json())
        response = sam_local_invoke(
            function_identifier=aws_worker_function_identifier, event=event,
        )
        assert isinstance(response, HandlerFunctionSuccessResponse)
        result_resp = s3.get_object(
            Bucket=boris_config.aws_s3_bucket_name, Key=calls[0].result_key
        )
        result_data = result_resp["Body"].read()
        assert pickle.loads(result_data) == 1 + 2

        status_blob = s3.get_object(
            Bucket=boris_config.aws_s3_bucket_name, Key=calls[0].status_key
        )
        status_data = status_blob["Body"].read()
        status_obj = CallStatus.parse_raw(status_data)
        assert status_obj.state == CallState.Success

        # Check second call
        event = json.loads(calls[1].json())
        response = sam_local_invoke(
            function_identifier=aws_worker_function_identifier, event=event,
        )
        assert isinstance(response, HandlerFunctionSuccessResponse)
        result_resp = s3.get_object(
            Bucket=boris_config.aws_s3_bucket_name, Key=calls[1].result_key
        )
        result_data = result_resp["Body"].read()
        assert pickle.loads(result_data) == 3 + 4

        status_blob = s3.get_object(
            Bucket=boris_config.aws_s3_bucket_name, Key=calls[1].status_key
        )
        status_data = status_blob["Body"].read()
        status_obj = CallStatus.parse_raw(status_data)
        assert status_obj.state == CallState.Success

    # Todo: test_ok_ignore_function_output

    @pytest.mark.parametrize(
        "tempdir",
        [
            {
                "err.py": dedent(
                    """
                    def func(payload):
                        raise ValueError('not enough cowbell')
                    """
                ),
            }
        ],
        indirect=True,
    )
    def test_err(
        self,
        tempdir,
        monkeypatch,
        s3,
        boris_config,
        sam_local_invoke,
        aws_worker_function_identifier,
    ):
        """Check that we can handle failed tasks

        Given
        -----
        A bundled function that raises an exception

        Expectations
        ------------
        - Only status.json is saved to storage
        - status.json contains exception status

        """
        monkeypatch.syspath_prepend(tempdir)
        func = getattr(import_module("err"), "func")

        bundler = Bundler(fn=func)
        bundler.package()

        args = ["hello world"]
        serializer = ListSerializer(items=args).serialize()

        job = Job(
            config=boris_config,
            call_start_pos=0,
            call_arg_byte_ranges=serializer.byte_ranges,
            store_function_output=True,
        )

        s3.put_object(
            Bucket=boris_config.aws_s3_bucket_name, Body=bundler.func, Key=job.func_key,
        )

        s3.put_object(
            Bucket=boris_config.aws_s3_bucket_name,
            Body=bundler.bundle,
            Key=job.bundle_key,
        )

        s3.put_object(
            Bucket=boris_config.aws_s3_bucket_name,
            Body=serializer.blob,
            Key=job.args_key,
        )

        calls = job.calls()

        event = json.loads(calls[0].json())
        response = sam_local_invoke(
            function_identifier=aws_worker_function_identifier, event=event,
        )

        assert isinstance(response, HandlerFunctionErrorResponse)
        assert len(response.errors) == 1
        assert response.errors[0].title == "not enough cowbell"

        status_key = calls[0].status_key

        status_resp = s3.get_object(
            Bucket=boris_config.aws_s3_bucket_name, Key=status_key
        )
        status_blob = status_resp["Body"].read()
        status = CallStatus.parse_raw(status_blob)

        assert status.state == CallState.Exception
        assert status.error == response.errors[0]

        call_prefix = "/".join(status_key.split("/")[:-1])
        call_prefix_list_objects_resp = s3.list_objects_v2(
            Bucket=boris_config.aws_s3_bucket_name, Prefix=call_prefix
        )
        call_prefix_objects = call_prefix_list_objects_resp["Contents"]
        assert len(call_prefix_objects) == 1

        object_filename = call_prefix_objects[0]["Key"].split("/")[-1]
        assert object_filename == "status.json"
