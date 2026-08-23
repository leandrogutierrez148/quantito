#!/usr/bin/env bash

set -euo pipefail

IMAGE_TAG="${1:-quantito-import-smoke}"

docker build -t "${IMAGE_TAG}" .
docker run --rm --entrypoint python "${IMAGE_TAG}" -c "import main, pipelines.real_time, pipelines.delayed, pipelines.eod; print('import-container-smoke-ok')"
