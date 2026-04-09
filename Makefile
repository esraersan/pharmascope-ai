install:
	pip install -e .

dev:
	pip install -e .
	docker compose up db -d
	sleep 3
	DATABASE_URL=postgresql://pharmascope:pharmascope@localhost:5432/pharmascope uvicorn pharmascope.api.main:app --reload --port 8000

streamlit:
	DATABASE_URL=postgresql://pharmascope:pharmascope@localhost:5432/pharmascope streamlit run demo/app.py --server.port 8501

test:
	pytest tests/unit/ -v
