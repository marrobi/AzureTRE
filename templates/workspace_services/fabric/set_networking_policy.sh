#!/bin/sh
set -e

# Sets the Fabric workspace inbound and outbound networking communication policy.
# Usage: set_networking_policy.sh <Allow|Deny> <workspace_id>
#
# Requires ARM_USE_MSI, ARM_TENANT_ID, ARM_CLIENT_ID, ARM_CLIENT_SECRET env vars.

ACTION="${1:?Usage: set_networking_policy.sh <Allow|Deny> <workspace_id>}"
WS_ID="${2:?Usage: set_networking_policy.sh <Allow|Deny> <workspace_id>}"

if [ "$ACTION" != "Allow" ] && [ "$ACTION" != "Deny" ]; then
  echo "ERROR: Action must be 'Allow' or 'Deny', got '$ACTION'"
  exit 1
fi

# Obtain a Fabric API access token
if [ "${ARM_USE_MSI}" = "true" ]; then
  TOKEN=$(curl -s 'http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://api.fabric.microsoft.com' \
    -H 'Metadata: true' | jq -r '.access_token')
else
  TOKEN=$(curl -s -X POST \
    "https://login.microsoftonline.com/${ARM_TENANT_ID}/oauth2/v2.0/token" \
    -d "client_id=${ARM_CLIENT_ID}&client_secret=${ARM_CLIENT_SECRET}&scope=https://api.fabric.microsoft.com/.default&grant_type=client_credentials" \
    | jq -r '.access_token')
fi

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  echo "ERROR: Failed to obtain Fabric API token"
  exit 1
fi

echo "Setting inbound and outbound networking policy to ${ACTION} for workspace ${WS_ID}"
HTTP_CODE=$(curl -s -o /tmp/policy_response.json -w '%{http_code}' -X PUT \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  "https://api.fabric.microsoft.com/v1/workspaces/${WS_ID}/networking/communicationPolicy" \
  -d "{\"inbound\":{\"publicAccessRules\":{\"defaultAction\":\"${ACTION}\"}},\"outbound\":{\"publicAccessRules\":{\"defaultAction\":\"${ACTION}\"}}}")

if [ "$HTTP_CODE" = "200" ]; then
  echo "Inbound and outbound networking policy set to ${ACTION}."
else
  echo "ERROR: Failed to set networking policy. HTTP ${HTTP_CODE}"
  cat /tmp/policy_response.json 2>/dev/null || true
  exit 1
fi
