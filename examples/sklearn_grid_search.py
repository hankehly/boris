import io
import logging
import os
import tempfile

import botocore.session
import numpy as np
from sklearn import datasets
from sklearn.model_selection import ParameterGrid, cross_validate, train_test_split
from sklearn.svm import SVC

import boris

logging.basicConfig()
logging.getLogger("botocore").setLevel(logging.INFO)
logging.getLogger("boris").setLevel(logging.DEBUG)


config = boris.Config(
    aws_access_key_id=os.getenv("BORIS_AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("BORIS_AWS_SECRET_ACCESS_KEY"),
    aws_s3_bucket_name=os.getenv("BORIS_AWS_S3_BUCKET_NAME"),
    aws_s3_bucket_region=os.getenv("BORIS_AWS_S3_BUCKET_REGION"),
    aws_lambda_region=os.getenv("BORIS_AWS_LAMBDA_REGION"),
    loglevel=boris.LogLevel.debug,
    backend=boris.Backend.Aws,
)

namespace = "sklearn_grid_search"


def create_and_upload_training_data():
    """

    """
    digits = datasets.load_digits()
    n_samples = len(digits.images)

    X = digits.images.reshape((n_samples, -1))
    y = digits.target

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=0
    )

    X_y_train = np.c_[X_train, y_train]

    s3 = botocore.session.get_session().create_client(
        service_name="s3",
        region_name=config.aws_s3_bucket_region,
        aws_access_key_id=config.aws_access_key_id.get_secret_value(),
        aws_secret_access_key=config.aws_secret_access_key.get_secret_value(),
    )

    with tempfile.TemporaryFile() as file:
        np.save(file, X_y_train)
        file.seek(0)
        s3.put_object(
            Bucket=config.aws_s3_bucket_name,
            Body=file,
            Key=f"examples/{namespace}/X_y_train.npy",
        )


def train_model(params):
    s3 = botocore.session.get_session().create_client("s3")
    res = s3.get_object(
        Bucket=config.aws_s3_bucket_name, Key=f"examples/{namespace}/X_y_train.npy"
    )
    train_data_bytes = res["Body"].read()
    X_y_train_ = np.load(io.BytesIO(train_data_bytes))
    X_train_, y_train_ = X_y_train_[:, :-1], X_y_train_[:, -1]
    cv_results = cross_validate(SVC(**params), X_train_, y_train_)
    return cv_results


if __name__ == "__main__":
    create_and_upload_training_data()

    tuned_parameters = [
        {"kernel": ["rbf"], "gamma": [1e-3, 1e-4], "C": [1, 10, 100, 1000]},
        {"kernel": ["linear"], "C": [1, 10, 100, 1000]},
    ]

    bex = boris.Executor(config=config)
    args = list(ParameterGrid(tuned_parameters))
    futures = bex.map(train_model, *args)
    result = futures[0].result()
    print(f"number of invocations: {len(args)}")
    print("first result:")
    print(result)
