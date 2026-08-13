#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
images=("ubuntu:24.04" "debian:bookworm-slim")

for base_image in "${images[@]}"; do
  safe_name="${base_image//[:\/]/-}"
  image_name="hermes-builder-e2e:$safe_name"
  echo "== build $base_image =="
  docker build \
    --build-arg "BASE_IMAGE=$base_image" \
    --tag "$image_name" \
    --file "$project_root/tests/docker/Dockerfile" \
    "$project_root"
  echo "== run $base_image =="
  docker run --rm \
    --env "HERMES_TEST_BASE=$base_image" \
    "$image_name"
done
