FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade -r requirements.txt

FROM python:3.12-slim

WORKDIR /

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local /usr/local

COPY ./app /app
COPY ./migrations /migrations
COPY ./scripts /scripts
COPY alembic.ini /alembic.ini

RUN chmod +x /scripts/startup.sh

EXPOSE 8000

CMD ["/bin/bash", "/scripts/startup.sh"]