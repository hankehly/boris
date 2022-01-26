from pydantic import AnyHttpUrl, BaseSettings, Field, SecretStr, validator

from .types import Backend, LogLevel, S3BucketName
from .utils import python_version as get_python_version


class Config(BaseSettings):
    """Boris library configuration

    To use non-default settings during execution, create a custom Config instance
    and pass to the executor.

    Backend specific settings are optional because the backend can change.

    """

    # Todo: dynamic validation of backend specific settings based on this value
    backend: Backend

    aws_access_key_id: SecretStr = None
    aws_secret_access_key: SecretStr = None
    aws_session_token: SecretStr = None
    aws_endpoint_url: AnyHttpUrl = None
    aws_s3_bucket_name: S3BucketName = None
    aws_s3_bucket_region: str = None
    aws_lambda_region: str = None

    loglevel: LogLevel = LogLevel.info

    # used to check for version compatibility between invocation and execution env
    python_version: str = Field(default_factory=get_python_version)

    class Config:
        use_enum_values = True
        env_prefix = "boris_"

    @validator(
        "aws_s3_bucket_name", "aws_s3_bucket_region", "aws_lambda_region", always=True,
    )
    def validate_backend_aws(cls, v, values, **kwargs):
        if values["backend"] == Backend.Aws:
            assert v, "this value is required to use the aws backend"
        return v
