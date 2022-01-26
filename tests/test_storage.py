import os

import pytest

from boris import Config
from boris.backends.aws.storage import Backend as S3
from boris.exceptions import MaxAttemptsExceeded, NoSuchBucket, PutObjectFailed
from boris.types import Backend, PutObject

BUCKET_NAME = "test123"


class TestS3:
    """Test cases for S3 storage class"""

    @pytest.fixture
    def config(self, moto_server):
        return Config(
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_endpoint_url=moto_server.docker_external_endpoint_url,
            aws_s3_bucket_name=BUCKET_NAME,
            aws_s3_bucket_region=os.getenv("AWS_REGION"),
            aws_lambda_region=os.getenv("AWS_REGION"),
            backend=Backend.Aws,
        )

    @pytest.mark.parametrize("s3_bucket", [BUCKET_NAME], indirect=True)
    def test_put_get_ok(self, config, s3_bucket):
        """Tests that our S3 storage client can upload/download objects"""
        storage = S3(config=config)
        storage.put_objects(
            objects=[
                PutObject(body=b"object_1", key="object_1_key"),
                PutObject(body=b"object_2", key="object_2_key"),
            ]
        )

        object_1 = storage.get_object(key="object_1_key")
        object_2 = storage.get_object(key="object_2_key")

        assert object_1 == b"object_1"
        assert object_2 == b"object_2"

    def test_no_such_bucket(self, config):
        storage = S3(config=config)
        with pytest.raises(NoSuchBucket):
            storage.put_objects(objects=[PutObject(body=b"test_body", key="test_key")])

    def test_put_object_failed(self, config):
        storage = S3(config=config)
        with pytest.raises(PutObjectFailed):
            storage.put_objects(objects=["hello world"])

    def test_get_max_attempts_reached(self, config):
        """We raise a MaxAttemptsExceeded exception after attempting N times"""
        storage = S3(config=config)
        with pytest.raises(MaxAttemptsExceeded):
            storage.get_object(key="test_key", max_attempts=1, retry_delay=0)
