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
	@trap 'kill 0' INT TERM EXIT; \
	if .venv/bin/python -c "import socket, sys; s = socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1', 8000)) == 0 else 1)"; then \
		echo 'Backend already running on 8000'; \
	else \
		(cd backend && ../.venv/bin/python main.py) & \
	fi; \
	cd frontend && npm run dev

test:
	.venv/bin/python -m pytest tests/ -v

build:
	cd electron && npm run build
