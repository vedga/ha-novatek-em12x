#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-}"
cd "$(dirname "$0")/.."

if [ -z "$VERSION" ]; then
  VERSION=$(python3 -c "import json;print(json.load(open('custom_components/novatek_em12x/manifest.json'))['version'])")
fi
TAG="v${VERSION}"

echo "== release check for ${TAG} =="

if [ -n "$(git status --porcelain)" ]; then
  echo "FAIL: working tree is not clean"; exit 1
fi
echo "ok: working tree clean"

MANIFEST_VERSION=$(python3 -c "import json;print(json.load(open('custom_components/novatek_em12x/manifest.json'))['version'])")
if [ "$MANIFEST_VERSION" != "$VERSION" ]; then
  echo "FAIL: manifest version ${MANIFEST_VERSION} != ${VERSION}"; exit 1
fi
echo "ok: manifest version ${VERSION}"

if grep -q "## ${VERSION}" CHANGELOG.md; then
  echo "ok: CHANGELOG has ${VERSION}"
else
  echo "FAIL: CHANGELOG has no section for ${VERSION}"; exit 1
fi

if git ls-remote --tags origin "refs/tags/${TAG}" | grep -q "refs/tags/${TAG}$"; then
  echo "FAIL: tag ${TAG} already exists on origin"; exit 1
fi
echo "ok: tag ${TAG} is free on origin"

ruff check .
python3 -m pytest -q
echo "ok: lint and tests passed"

echo "ALL CHECKS PASSED. Safe to push and create release ${TAG}."
