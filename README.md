# boris

![](https://github.com/hankehly/boris/workflows/py-test/badge.svg)

## What is boris?

boris is a distributed processing tool that uses "serverless" cloud infrastructure to run programs in parallel.
Currently AWS is the only supported provider.

boris borrows heavily from [lithops](https://github.com/lithops-cloud/lithops) implementation.

### When should I use boris?

boris basically executes a function with 1 or more parameter combinations. This makes it a good candidate for
hyper-parameter optimization tasks like grid-searches or training many machine-learning models in parallel.

## Getting Started

### Deploy boris to your cloud provider

To get started with boris, run the appropriate `make` command to build and deploy your cloud resources. Later, we will
invoke a function using this infrastructure.

**Note:** The AWS backend requires the SAM executable. You can download it
here ([Linux](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install-linux.html)) ([macOS](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install-mac.html))

**Note:** The AWS backend requires an ECR image repository.

```bash
make build_aws
make build_deploy
```

#### Create a function

boris invokes a python function multiple times – each time with different parameter values. The target function can have
dependencies on builtin libraries or 3rd party libraries.

```py
import time


def add(data):
    time.sleep(1)
    return data["x"] + data["y"]
```

#### Invoke a function

Create an `Executor` instance from a boris configuration object. Call the executor's `map` method to begin execution.
boris will package your function and its dependencies, upload it to storage and start function execution on the
configured compute backend.

```py
import boris

config = boris.Config(
    backend=boris.Backend.Aws,
    aws_secret_access_key="..."
)

bex = boris.Executor(config=config)

args = [
    {"x": 1, "y": 1},
    {"x": 2, "y": 2},
    {"x": 3, "y": 3}
]

futures = bex.map(add, *args)
futures[0].result()  # 2
```

### Concepts

Todo: describe flow

### Limitations

- Libraries that use special initialization logic (eg. django) will likely cause boris to fail.
- To prevent errors when packaging functions that reference libs with c-extensions, boris uses the following versions.

| package | version |
|:-|:--|
| cloudpickle | 1.6.0 |
| joblib | 0.17.0 |
| numpy | 1.19.4 |
| pandas | 1.1.4 |
| psycopg2-binary | 2.8.6 |
| pydantic | 1.7.3 |
| python-dateutil | 2.8.1 |
| pytz | 2020.4 |
| scikit-learn | 0.23.2 |
| scipy | 1.5.4 |
| six | 1.15.0 |
| threadpoolctl | 2.1.0 |


### Cloud Resources

#### AWS

- 3 Lambda functions **per python version**
- 2 S3 buckets
