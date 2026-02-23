# Makefile for IVY AI Counsellor

.PHONY: help install install-dev test lint format clean dev build up down logs backend frontend

help:
	@echo "IVY AI Counsellor - Available Commands:"
	@echo ""
	@echo "  make install       - Install production dependencies"
	@echo "  make install-dev   - Install development dependencies"
	@echo "  make test          - Run tests with coverage"
	@echo "  make lint          - Run code linters"
	@echo "  make format        - Format code with black"
	@echo "  make clean         - Remove generated files"
	@echo ""
	@echo "  make dev           - Start development environment (Docker)"
	@echo "  make build         - Build Docker images"
	@echo "  make up            - Start containers"
	@echo "  make down          - Stop containers"
	@echo "  make logs          - View container logs"
	@echo ""
	@echo "  make backend       - Run backend locally"
	@echo "  make frontend      - Run frontend locally"

install:
	cd backend && pip install -r requirements.txt

install-dev:
	cd backend && pip install -r requirements/dev.txt
	cd frontend && npm install

test:
	cd backend && pytest tests/ -v --cov=app --cov-report=html --cov-report=term

lint:
	cd backend && ruff check app/ tests/
	cd backend && mypy app/

format:
	cd backend && black app/ tests/
	cd backend && ruff check --fix app/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf backend/htmlcov
	rm -rf backend/.pytest_cache
	rm -rf backend/.mypy_cache
	rm -rf frontend/node_modules
	rm -rf frontend/build

dev:
	docker-compose up

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm start
