.PHONY: setup lint test demo-offline demo-retrieval knowledge-plan schemas audit serve check-infra

TERRAFORM ?= terraform

setup:
	uv sync --locked

lint:
	uv run --locked python scripts/check.py --lint-only

test:
	uv run --locked pytest --cov --cov-report=term-missing

demo-offline:
	uv run --locked python scripts/demo_offline.py

demo-retrieval:
	uv run --locked python scripts/demo_retrieval.py

knowledge-plan:
	uv run --locked terramind-knowledge plan

schemas:
	uv run --locked python scripts/export_schemas.py

audit:
	uv run --locked python -c "from pathlib import Path; Path('artifacts').mkdir(exist_ok=True)"
	uv export --locked --all-extras --no-emit-project --format requirements-txt --output-file artifacts/audit-requirements.txt --quiet
	uv run --locked pip-audit --no-deps --disable-pip --requirement artifacts/audit-requirements.txt

serve:
	uv run --locked --extra api python -m terramind.api

check-infra:
	uv run --locked python scripts/check_infrastructure.py --terraform "$(TERRAFORM)" --scan
