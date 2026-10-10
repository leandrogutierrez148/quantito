#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${1:-quantito:smoke-test}"

echo "Building smoke test image: ${IMAGE_TAG}"
docker build -t "${IMAGE_TAG}" .

echo "Running import container smoke test..."
docker run --rm --entrypoint python "${IMAGE_TAG}" -c "import main, quantito, quantito.server; print('import-container-smoke-ok')"

echo "Smoke test passed successfully."
