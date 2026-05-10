install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

lint:
	ruff check .
	ruff format --check .

typecheck:
	mypy chirp_to_libib kindle_to_libib lib

test:
	pytest

coverage:
	pytest --cov=chirp_to_libib --cov=kindle_to_libib --cov=lib --cov-report=term-missing
