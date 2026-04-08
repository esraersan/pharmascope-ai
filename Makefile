dev:
	docker compose up db -d
	sleep 3
	DATABASE_URL=postgresql://pharmascope:pharmascope@localhost:5432/pharmascope uvicorn pharmascope.api.main:app --reload --port 8000

test:
	pytest tests/unit/ -v
