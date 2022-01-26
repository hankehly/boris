import logging
import os
import time

import boris
from examples.utils import Arg

logging.basicConfig()
logging.getLogger("botocore").setLevel(logging.INFO)
logging.getLogger("boris").setLevel(logging.DEBUG)


def bench(arg: dict) -> dict:
    model = Arg.parse_obj(arg)
    time.sleep(model.sleep_seconds)
    return model.dict()


def run(*, n_calls: int = 1, sleep_seconds: int = 5):
    """
    Arguments
    ---------
    n_calls: int (default 1)
        number of invocations

    sleep_seconds: int (default 5)
        how long each invocation should take

    """
    config = boris.Config(
        aws_access_key_id=os.getenv("BORIS_AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("BORIS_AWS_SECRET_ACCESS_KEY"),
        aws_s3_bucket_name=os.getenv("BORIS_AWS_S3_BUCKET_NAME"),
        aws_s3_bucket_region=os.getenv("BORIS_AWS_S3_BUCKET_REGION"),
        aws_lambda_region=os.getenv("BORIS_AWS_LAMBDA_REGION"),
        loglevel=boris.LogLevel.debug,
        backend=boris.Backend.Aws,
    )

    bex = boris.Executor(config=config)
    args = [
        {"sleep_seconds": sleep_seconds, "value": f"{i:05d}"} for i in range(n_calls)
    ]

    futures = bex.map(bench, *args)
    result_1 = futures[0].result()

    print(
        f"done <n_calls: {n_calls}, n futures: {len(futures)}, first result: {result_1}>"
    )


if __name__ == "__main__":
    run(n_calls=2, sleep_seconds=1)
