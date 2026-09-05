# AegisForge worker image (AF-003 / C04).
#
# Runs the frozen /v1 worker API from backend/contracts. It owns no canonical
# state: the coordinator persists the job, this service runs one bounded attempt.
#
# Base pinned by digest from OD-08 (docs/architecture.md 8.1), linux/amd64.
FROM python:3.13-slim-bookworm@sha256:2f2e5a876c71a6757f55ec57f2add0225ddaf01c802a33fcc29073943f94d907 AS worker-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# --require-hashes: every wheel must match provenance.json or the build fails.
COPY backend/worker-image/requirements.lock /tmp/requirements.lock
RUN python -m pip --isolated install --no-cache-dir --only-binary=:all: \
    --require-hashes --no-deps --index-url https://pypi.org/simple \
    -r /tmp/requirements.lock \
    && python -m pip check

COPY backend/contracts/ /app/backend/contracts/
COPY backend/worker/ /app/backend/worker/
COPY backend/worker-image/provenance.json /app/provenance.json

# Offline build-time checks. --network=none proves they contact nothing.
# Offline behavioural checks. --network=none proves they contact nothing.
# AEGIS_WORKER_TOKEN is a build-time value for the tests only; the runtime
# credential is supplied at deployment and this one never reaches the image.
RUN --network=none AEGIS_WORKER_TOKEN=build-time-check-token-not-a-secret-000000 \
    AEGIS_NODE_ID=22222222-2222-4222-8222-222222222222 \
    python -m unittest -q \
      backend.contracts.test_contracts \
      backend.worker.test_worker_runtime \
      backend.worker.test_worker_app \
      backend.worker.test_executor

# Non-root, matching the security boundary for worker execution.
USER 10001:10001
EXPOSE 8443

# The worker refuses to start without a credential, so it cannot run open.
ENV AEGIS_RUNTIME_HOST=http://127.0.0.1:11434 \
    AEGIS_MODEL=qwen3.5:4b-q4_K_M \
    AEGIS_NUM_CTX=4096 \
    AEGIS_NUM_PREDICT=2048

CMD ["python", "-m", "uvicorn", "backend.worker.app:app", \
     "--host", "0.0.0.0", "--port", "8443", "--no-server-header"]
