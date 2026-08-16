FROM python:3.12-slim

WORKDIR /app

# psycopg2-binary needs these at runtime on slim images in some cases;
# libpq5 covers it without needing full build tooling.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Render (and most PaaS) inject $PORT — default to 8000 for local docker run
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
