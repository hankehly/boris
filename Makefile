lint:
	poetry check
	# adding flake8 args here instead of creating new config file
	poetry run flake8 --ignore E203,E266,E501,W503 --max-line-length 88 --select B,C,E,F,W,T4,B9,R701 --radon-max-cc 5 boris
	poetry run flake8 --ignore E203,E266,E501,W503 --max-line-length 88 --select B,C,E,F,W,T4,B9,R701 --radon-max-cc 5 --radon-no-assert tests

test:
	@if [ -z $$SKIP_BUILD ]; then ./scripts/build_aws; fi
	poetry run tox --parallel --parallel-live -- -vv -s --durations=10

test_py37:
	@if [ -z $$SKIP_BUILD ]; then BORIS_TEMPLATE_SUFFIX=py37 ./scripts/build_aws; fi
	poetry run tox -e py37 -- -vv -s --durations=10

test_py38:
	@if [ -z $$SKIP_BUILD ]; then BORIS_TEMPLATE_SUFFIX=py38 ./scripts/build_aws; fi
	poetry run tox -e py38 -- -vv -s --durations=10

reformat:
	poetry run isort --recursive boris tests examples
	poetry run black boris tests examples

build_aws:
	./scripts/build_aws

build_aws_py37:
	BORIS_TEMPLATE_SUFFIX=py37 ./scripts/build_aws

build_aws_py38:
	BORIS_TEMPLATE_SUFFIX=py37 ./scripts/build_aws

deploy_aws:
	./scripts/deploy_aws

aws_destroy:
	#aws s3 rm --recursive s3://{content bucket name}/
	aws cloudformation delete-stack --stack-name boris-handler-stack
