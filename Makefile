install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

lint:
	ruff check .
	ruff format --check .

typecheck:
	mypy chirp_to_libib

test:
	pytest

coverage:
	pytest --cov=chirp_to_libib --cov-report=term-missing
