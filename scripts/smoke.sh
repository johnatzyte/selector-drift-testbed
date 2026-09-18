#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8811}"
BASE="http://localhost:${PORT}"
# Fixed key for the duration of the smoke test, so we can sign the mutations below.
export SHOP_API_KEY="${SHOP_API_KEY:-smoke-$(date +%s)}"
AUTH=(-H "X-API-Key: ${SHOP_API_KEY}")

echo "==> tests"
uv run --locked pytest -q

echo "==> container"
docker compose up -d --build --wait

cleanup() { docker compose down >/dev/null 2>&1 || true; }
trap cleanup EXIT

curl -fsS "${BASE}/" >/dev/null
curl -fsS "${BASE}/coffee/beans/" >/dev/null
curl -fsS "${BASE}/assets/site.css" >/dev/null

# An unsigned mutation must be refused before anything else is trusted.
test "$(curl -s -o /dev/null -w '%{http_code}' -X PATCH "${BASE}/api/selectors" \
  -H 'content-type: application/json' -d '{"title_class": "item-name"}')" = "401"

# The whole demo in four calls: rename a class, prove it moved in both the markup
# and the stylesheet, then put it back.
curl -fsS -X PATCH "${BASE}/api/selectors" "${AUTH[@]}" \
  -H 'content-type: application/json' \
  -d '{"title_class": "item-name"}' >/dev/null

curl -fsS "${BASE}/coffee/beans/" | grep -q 'class="item-name"'
curl -fsS "${BASE}/assets/site.css" | grep -q '\.item-name'
! curl -fsS "${BASE}/coffee/beans/" | grep -q 'class="product-title"'

curl -fsS -X POST "${BASE}/api/selectors/reset" "${AUTH[@]}" >/dev/null
curl -fsS "${BASE}/coffee/beans/" | grep -q 'class="product-title"'

echo "Smoke test passed"
