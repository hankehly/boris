import random
import subprocess
import time
from pathlib import Path
from typing import Union

from pydantic import BaseModel, Field, constr

container_name_regex = "[a-zA-Z0-9]+"


class MotoServerConfig(BaseModel):
    """aws backend test server configuration

    Container name must be valid according to botocore.utils.is_valid_endpoint_url
    hence the regex.

    The internal container port is always 5000.

    """

    network: str
    container: constr(strict=True, regex=container_name_regex)
    port_external: int = Field(default_factory=lambda: random.randint(5000, 8000))
    port_internal: int = 5000

    @property
    def docker_internal_endpoint_url(self) -> str:
        return f"http://{self.container}:{self.port_internal}"

    @property
    def docker_external_endpoint_url(self) -> str:
        return f"http://127.0.0.1:{self.port_external}"


def destroy_s3_bucket(s3, *, name: str):
    """Deletes all objects within a bucket, then deletes the bucket itself"""
    resp = s3.list_objects_v2(Bucket=name)
    keys = [item["Key"] for item in resp["Contents"]]
    s3.delete_objects(
        Bucket=name, Delete={"Objects": [{"Key": key} for key in keys]},
    )
    s3.delete_bucket(Bucket=name)


def write_recursive(*, path: str, content: Union[dict, str], parent: Path) -> None:
    """Writes `content` at `parent.path` creating parent directories if necessary

    When `content` is type dict, we recurse. When `content` is type str, we create
    parent dirs and write `content` to `parent / path`

        "B": {                        << when `path` is B, we recurse
            "test.py": "import json"  << when `path` is test.py, we write to B/test.py
        }

    Examples
    --------
    Writes "import.json" to /tmp/A/a.py and creates all parent dirs if necessary
    >>> write_recursive(path="A", content={"a.py": "import json"}, parent=Path("/tmp")

    """
    if isinstance(content, dict):
        for child_path, child_content in content.items():
            write_recursive(
                path=child_path, content=child_content, parent=parent.joinpath(path)
            )
    elif isinstance(content, str):
        parent.mkdir(parents=True, exist_ok=True)
        parent.joinpath(path).write_text(content)
    else:
        raise ValueError(
            f"invalid `content` type "
            f"<expected: Union[dict, str], actual: {content.__class__.__name__}>"
        )


def wait_until_healthy(*, container_id: str, max_attempts: int = 15) -> None:
    """Checks health of container_id a maximum `max_attempts` times until healthy

    Raises
    ------
    MaxAttemptsReached
        if number of attempts

    Todo: backoff wait time
    Todo: exit after unhealthy status?

    """
    for attempt in range(max_attempts):
        args = [
            "docker",
            "inspect",
            "--format='{{if .Config.Healthcheck}}{{print .State.Health.Status}}{{end}}'",
            container_id,
        ]
        proc = subprocess.run(args, stdout=subprocess.PIPE)
        resp = proc.stdout.decode().strip().strip("'")

        if resp == "healthy":
            print("service is healthy")
            return
        else:
            print(
                f"service is {resp}. waiting 1 second before checking again "
                f"(attempts: {attempt + 1})"
            )
            time.sleep(1)

    raise Exception(f"wait limit reached ({max_attempts} seconds)")
