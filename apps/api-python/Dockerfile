FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml ./
COPY packages/py/domain packages/py/domain
COPY packages/py/market packages/py/market
COPY packages/py/infrastructure packages/py/infrastructure
COPY apps/api-python apps/api-python

RUN pip install uv && uv sync --directory apps/api-python --frozen 2>/dev/null || \
    pip install ./packages/py/domain ./packages/py/market ./packages/py/infrastructure ./apps/api-python

FROM python:3.12-slim AS runtime

WORKDIR /app
COPY --from=builder /usr/local /usr/local
COPY apps/api-python/src/bolsa_api /app/bolsa_api
COPY packages/py/domain/src/bolsa_domain /app/bolsa_domain
COPY packages/py/market/src/bolsa_market /app/bolsa_market
COPY packages/py/infrastructure/src/bolsa_infrastructure /app/bolsa_infrastructure

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["uvicorn", "bolsa_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
