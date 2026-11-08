.PHONY: setup lint test demo-offline schemas audit

setup:
	uv sync --locked

lint:
	uv run --locked python scripts/check.py --lint-only

test:
	uv run --locked pytest --cov --cov-report=term-missing

demo-offline:
	uv run --locked python scripts/demo_offline.py

schemas:
	uv run --locked python scripts/export_schemas.py

audit:
	uv run --locked python -c "from pathlib import Path; Path('artifacts').mkdir(exist_ok=True)"
	uv export --locked --no-emit-project --format requirements-txt --output-file artifacts/audit-requirements.txt --quiet
	uv run --locked pip-audit --no-deps --disable-pip --requirement artifacts/audit-requirements.txt
