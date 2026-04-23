.PHONY: install dev test build

install:
	pip install -r requirements.txt
	cd frontend && npm install
	cd electron && npm install

dev:
	cd electron && npm run dev

dev-api:
	cd backend && python main.py

dev-web:
	cd frontend && npm run dev

test:
	python -m pytest tests/ -v

build:
	cd electron && npm run build
