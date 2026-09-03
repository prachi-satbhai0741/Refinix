# C04 build inputs only. This image exports the contract; it is not a worker API.
# The actual worker entrypoint is added after requester acceptance of C03.
FROM python:3.13-slim-bookworm@sha256:2f2e5a876c71a6757f55ec57f2add0225ddaf01c802a33fcc29073943f94d907 AS worker-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY backend/worker-image/requirements.lock /tmp/requirements.lock
RUN python -m pip --isolated install --no-cache-dir --only-binary=:all: \
    --require-hashes --no-deps --index-url https://pypi.org/simple \
    -r /tmp/requirements.lock \
    && python -m pip check

COPY backend/contracts/ /app/backend/contracts/
COPY backend/worker-image/provenance.json /app/provenance.json

# Existing synthetic contract checks; no server or model is contacted.
RUN --network=none python -m unittest backend.contracts.test_contracts -q \
    && python -c "from fastapi import FastAPI; import uvicorn; assert FastAPI(docs_url=None, redoc_url=None).openapi()['openapi']"

USER 10001:10001
CMD ["python", "-m", "backend.contracts"]
