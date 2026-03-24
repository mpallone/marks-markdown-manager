.PHONY: test clean

test:
	venv/bin/pytest

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name '*.egg-info' -exec rm -rf {} +
