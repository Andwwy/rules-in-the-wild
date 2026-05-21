FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY rules_models /app/rules_models
COPY rules_labeling/backend /app/rules_labeling/backend

WORKDIR /app/rules_labeling/backend
RUN uv sync --frozen

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uv", "run", "rules-labeling-api", "--db", "md:rules_in_the_wild", "--host", "0.0.0.0", "--port", "8000"]
