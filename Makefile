.PHONY: format lint test all

format:
	black src tests

lint:
	pylint src

test:
	pytest tests

all: format lint test
