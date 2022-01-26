import json
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Callable, Union

import botocore.session
import pytest

from boris.types import HandlerFunctionErrorResponse, HandlerFunctionSuccessResponse
from boris.utils import python_version
from tests.utils import (
    MotoServerConfig,
    destroy_s3_bucket,
    wait_until_healthy,
    write_recursive,
)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def tempdir(tmp_path_factory, request):
    """Generates a dir structure from dict configuration and destroys on teardown.

    TODO: Refactor to use tmp_path instead of tmp_path_factory

    Yields
    ------
    Path
        The root path of the temp dir

    Examples
    --------
    >>> @pytest.mark.parametrize(
    >>>    "tempdir",
    >>>    [{
    >>>        "A": {
    >>>            "a.py": "import json"
    >>>        },
    >>>        "__init__.py": "",
    >>>    }],
    >>>    indirect=True,
    >>> )
    >>> def test_my_function(tempdir):
    >>>     pass

    """
    basename = tempfile.gettempprefix()
    root = tmp_path_factory.mktemp(basename)
    for path, content in request.param.items():
        write_recursive(path=path, content=content, parent=root)
    yield root
    shutil.rmtree(root)


@pytest.fixture(scope="function")
def sam_local_invoke(moto_server) -> Callable:
    """Provides a helper function to invoke `sam local invoke` with common args

    Returns
    -------
    Callable
        an invocation function that calls `sam local invoke` on the provided function
        with the provided event input

    Examples
    --------
    >>> def test(sam_local_invoke):
    >>>     sam_local_invoke(
    >>>         function_identifier="BorisWorkerPy37",
    >>>         event={
    >>>             "key": "value"
    >>>         }
    >>>     )

    Raises
    ------
    ValueError
        if the response body from lambda does not match the structure of either
        SuccessResponse or ErrorResponse

    """

    def invoke(
        *, function_identifier: str, event: dict
    ) -> Union[HandlerFunctionSuccessResponse, HandlerFunctionErrorResponse]:
        with tempfile.TemporaryFile() as stdin:
            event = json.dumps(event).encode("UTF8")

            stdin.write(event)
            stdin.seek(0)

            args = [
                "sam",
                "local",
                "invoke",
                function_identifier,
                "--event",
                "-",
                "--docker-network",
                moto_server.network,
            ]

            logger.info(" ".join(args))
            proc = subprocess.run(args, stdin=stdin, stdout=subprocess.PIPE)
            body = json.loads(proc.stdout)

            if "data" in body:
                return HandlerFunctionSuccessResponse.parse_obj(body)
            elif "errors" in body:
                return HandlerFunctionErrorResponse.parse_obj(body)

            raise ValueError(
                f"body structure does not match SuccessResponse or ErrorResponse "
                f"<body: {body}>"
            )

    return invoke


@pytest.fixture(scope="session")
def mock_aws_credentials():
    """Mocked AWS Credentials for moto server

    """
    os.environ["AWS_ACCESS_KEY_ID"] = "test"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
    os.environ["AWS_SESSION_TOKEN"] = "test"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_REGION"] = "us-east-1"


@pytest.fixture(scope="session")
def local_python_version() -> str:
    return python_version(sep="")


@pytest.fixture(scope="session")
def moto_server(local_python_version, mock_aws_credentials):
    """Starts and stops a mock AWS server docker container

    Yields
    ------
    MotoServerConfig

    """
    config = MotoServerConfig(
        network=f"boris-py{local_python_version}",
        container=f"motoserver-boris-py{local_python_version}",
    )

    print(config.json())
    subprocess.run(["docker", "network", "create", config.network])
    subprocess.run(
        [
            "docker",
            "run",
            f"--name={config.container}",
            "--detach",
            "--rm",
            f"--network={config.network}",
            f"--publish={config.port_external}:{config.port_internal}",
            "--health-cmd=python3 /moto/wait_for.py",
            "--health-interval=1s",
            "--health-retries=10",
            "--health-timeout=5s",
            "motoserver/moto:1.3.16",
        ],
    )

    wait_until_healthy(container_id=config.container)
    yield config

    # Todo: log fixture
    print(f"stopping container '{config.container}'")
    subprocess.run(["docker", "stop", config.container])

    print(f"removing network '{config.network}'")
    subprocess.run(["docker", "network", "rm", config.network])


@pytest.fixture(scope="session")
def aws_dispatch_function_identifier(local_python_version) -> str:
    return "BorisDispatchPy" + local_python_version


@pytest.fixture(scope="session")
def aws_main_function_identifier(local_python_version) -> str:
    return "BorisMainPy" + local_python_version


@pytest.fixture(scope="session")
def aws_worker_function_identifier(local_python_version) -> str:
    return "BorisWorkerPy" + local_python_version


@pytest.fixture(scope="function")
def s3(moto_server):
    """Provides a botocore s3 client setup with moto server configuration"""
    yield botocore.session.get_session().create_client(
        service_name="s3",
        region_name=os.getenv("AWS_REGION"),
        endpoint_url=moto_server.docker_external_endpoint_url,
    )


@pytest.fixture(scope="function")
def s3_bucket(s3, request):
    """Performs setup and teardown of an S3 bucket

    Yields
    ------
    str
        the name of the created s3 bucket

    """
    s3.create_bucket(Bucket=request.param)
    yield request.param
    destroy_s3_bucket(s3, name=request.param)
