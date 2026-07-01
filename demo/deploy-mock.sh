#!/usr/bin/env bash
# Deploy the MOCK Azure TRE UI (no auth, no API — client-side mock data) to an
# Azure Static Web App for sharing as a demo. Free SKU ($0). Idempotent.
#
# Usage: ./demo/deploy-mock.sh [resource-group] [app-name] [region]
set -euo pipefail

RG="${1:-rg-tre-billing-demo}"
APP="${2:-tre-billing-demo}"
REGION="${3:-westeurope}"   # SWA Free is available in: westus2, centralus, eastus2, westeurope, eastasia
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_DIR="$REPO_ROOT/ui/app"
DIST="$UI_DIR/dist"

echo "==> Building mock UI (VITE_MOCK=true)"
( cd "$UI_DIR" && npm run build:mock )

echo "==> Adding SPA fallback config"
cp "$REPO_ROOT/demo/staticwebapp.config.json" "$DIST/staticwebapp.config.json"

echo "==> Ensuring resource group '$RG'"
az group create -n "$RG" -l "$REGION" -o none

echo "==> Ensuring Static Web App '$APP'"
if ! az staticwebapp show -n "$APP" -g "$RG" -o none 2>/dev/null; then
  az staticwebapp create -n "$APP" -g "$RG" -l "$REGION" --sku Free -o none
fi

echo "==> Fetching deployment token"
TOKEN="$(az staticwebapp secrets list -n "$APP" -g "$RG" --query "properties.apiKey" -o tsv)"

echo "==> Deploying static content"
npx --yes @azure/static-web-apps-cli@latest deploy "$DIST" \
  --deployment-token "$TOKEN" \
  --env production

URL="https://$(az staticwebapp show -n "$APP" -g "$RG" --query defaultHostname -o tsv)"
echo ""
echo "==> Deployed: $URL"
echo "    Billing dashboard: $URL/billing"
echo "    Standalone demo:   $URL/billing-demo"
