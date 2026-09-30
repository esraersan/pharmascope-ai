FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ ./src/
COPY demo/ ./demo/
RUN pip install --no-cache-dir .

CMD ["sh", "-c", "pharmascope init-db && exec uvicorn pharmascope.api.main:app --host 0.0.0.0 --port 8000"]
