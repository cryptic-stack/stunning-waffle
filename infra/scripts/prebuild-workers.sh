#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"

cd "${repo_root}"

build_image() {
  local tag="$1"
  local dockerfile="$2"
  printf 'building %s...\n' "${tag}"
  docker build -t "${tag}" -f "${dockerfile}" .
}

build_image "foss-browserlab-chromium-worker:latest" "images/chromium/Dockerfile"
build_image "foss-browserlab-firefox-worker:latest" "images/firefox/Dockerfile"
build_image "foss-browserlab-brave-worker:latest" "images/brave/Dockerfile"
build_image "foss-browserlab-edge-worker:latest" "images/edge/Dockerfile"
build_image "foss-browserlab-vivaldi-worker:latest" "images/vivaldi/Dockerfile"
build_image "foss-browserlab-ubuntu-xfce-worker:latest" "images/ubuntu-xfce/Dockerfile"
build_image "foss-browserlab-kali-xfce-worker:latest" "images/kali-xfce/Dockerfile"
