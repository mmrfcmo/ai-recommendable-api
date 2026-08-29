FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render uses the PORT env var (default 10000 if not set)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}
