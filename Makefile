.PHONY: install dev test build

install:
	uv venv
	uv pip install --python .venv/bin/python -r requirements.txt
	cd frontend && npm install
	cd electron && npm install

dev:
	cd electron && npm run dev

dev-api:
	cd backend && ../.venv/bin/python main.py

dev-web:
	cd frontend && npm run dev

test:
	.venv/bin/python -m pytest tests/ -v

build:
	cd electron && npm run build
