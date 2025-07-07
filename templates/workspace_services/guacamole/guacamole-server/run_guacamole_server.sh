#!/bin/bash

# Load environment variables from Terraform output
# change directory to script directory
cd "$(dirname "$0")" || exit

# Define DIR for load_and_validate_env.sh (should point to devops/scripts)
DIR="$(cd "$(dirname "$0")/../../../../devops/scripts" && pwd)"
export DIR

# Change to root directory to find config.yaml, then load environment variables
cd "$(dirname "$0")/../../../.." || exit
source devops/scripts/load_and_validate_env.sh
# Change back to the guacamole-server directory
cd templates/workspace_services/guacamole/guacamole-server || exit

# Set additional environment variables for Guacamole
export WEBSITES_PORT=8080
export TENANT_ID=$AZURE_TENANT_ID
export KEYVAULT_URL=$KEYVAULT_URI
export API_URL="$TRE_URL"
export API_CLIENT_ID=$API_CLIENT_ID
export MANAGED_IDENTITY_CLIENT_ID="your-managed-identity-client-id"
export APPLICATIONINSIGHTS_CONNECTION_STRING=$APPLICATIONINSIGHTS_CONNECTION_STRING
export APPLICATIONINSIGHTS_INSTRUMENTATION_LOGGING_LEVEL="INFO"
export GUAC_DISABLE_COPY="false"
export GUAC_DISABLE_PASTE="false"
export GUAC_ENABLE_DRIVE="true"
export GUAC_DRIVE_NAME="MyDrive"
export GUAC_DRIVE_PATH="/drive"
export GUAC_DISABLE_DOWNLOAD="false"
export GUAC_DISABLE_UPLOAD="false"
# Azure TRE Authentication settings (for workspace-specific authentication)
export TRE_API_ENDPOINT="$API_URL"
export TRE_API_CLIENT_ID="$API_CLIENT_ID"
export TRE_API_CLIENT_SECRET="$API_CLIENT_SECRET"
export JWKS_URI="https://login.microsoftonline.com/$AZURE_TENANT_ID/discovery/v2.0/keys"
export AZURE_AUTHORITY="https://login.microsoftonline.com/$AZURE_TENANT_ID"
export TRE_AUTH_FLOW="authorization_code"
export TRE_TOKEN_ENDPOINT="https://login.microsoftonline.com/${AZURE_TENANT_ID}/oauth2/v2.0/token"
# Enable URL-based workspace authentication
export TRE_WORKSPACE_AUTH_ENABLED="true"
export TRE_WORKSPACE_URL_PARAM="workspace_client_id"

# Legacy OpenID settings (kept as fallback for direct access)
export GUAC_OPENID_AUTHORIZATION_ENDPOINT="https://login.microsoftonline.com/${AZURE_TENANT_ID}/oauth2/v2.0/authorize"
export GUAC_OPENID_JWKS_ENDPOINT="https://login.microsoftonline.com/${AZURE_TENANT_ID}/discovery/v2.0/keys"
export GUAC_OPENID_ISSUER="https://login.microsoftonline.com/${AZURE_TENANT_ID}/v2.0"
# Note: OPENID_CLIENT_ID removed - now using workspace_client_id URL parameter exclusively
export GUAC_OPENID_REDIRECT_URI="http://localhost:8080/guacamole/"
export GUAC_OPENID_USERNAME_CLAIM_TYPE="preferred_username"
export GUAC_OPENID_GROUPS_CLAIM_TYPE="roles"
# OpenID Connect configuration for Guacamole (fallback implicit flow)
export GUAC_OPENID_SCOPE="openid profile email"
export GUAC_OPENID_MAX_TOKEN_VALIDITY="300"
# Note: No client secret for implicit flow

# Build the Docker image
sudo docker build -t microsoft/azuretre/guacamole-server:latest -f ./docker/Dockerfile .

# Run the Docker container
sudo docker run -it \
  -p $WEBSITES_PORT:8080 \
  -e WEBSITES_PORT="$WEBSITES_PORT" \
  -e TENANT_ID="$TENANT_ID" \
  -e KEYVAULT_URL="$KEYVAULT_URL" \
  -e API_URL="$API_URL" \
  -e API_CLIENT_ID="$API_CLIENT_ID" \
  -e MANAGED_IDENTITY_CLIENT_ID="$MANAGED_IDENTITY_CLIENT_ID" \
  -e APPLICATIONINSIGHTS_CONNECTION_STRING="$APPLICATIONINSIGHTS_CONNECTION_STRING" \
  -e APPLICATIONINSIGHTS_INSTRUMENTATION_LOGGING_LEVEL="$APPLICATIONINSIGHTS_INSTRUMENTATION_LOGGING_LEVEL" \
  -e GUAC_DISABLE_COPY="$GUAC_DISABLE_COPY" \
  -e GUAC_DISABLE_PASTE="$GUAC_DISABLE_PASTE" \
  -e GUAC_ENABLE_DRIVE="$GUAC_ENABLE_DRIVE" \
  -e GUAC_DRIVE_NAME="$GUAC_DRIVE_NAME" \
  -e GUAC_DRIVE_PATH="$GUAC_DRIVE_PATH" \
  -e GUAC_DISABLE_DOWNLOAD="$GUAC_DISABLE_DOWNLOAD" \
  -e GUAC_DISABLE_UPLOAD="$GUAC_DISABLE_UPLOAD" \
  -e TRE_API_ENDPOINT="$TRE_API_ENDPOINT" \
  -e TRE_API_CLIENT_ID="$TRE_API_CLIENT_ID" \
  -e TRE_API_CLIENT_SECRET="$TRE_API_CLIENT_SECRET" \
  -e TRE_AUTH_FLOW="$TRE_AUTH_FLOW" \
  -e TRE_TOKEN_ENDPOINT="$TRE_TOKEN_ENDPOINT" \
  -e TRE_WORKSPACE_AUTH_ENABLED="$TRE_WORKSPACE_AUTH_ENABLED" \
  -e TRE_WORKSPACE_URL_PARAM="$TRE_WORKSPACE_URL_PARAM" \
  -e JWKS_URI="$JWKS_URI" \
  -e AZURE_AUTHORITY="$AZURE_AUTHORITY" \
  -e TRE_URL="http://localhost:8080" \
  -e OPENID_AUTHORIZATION_ENDPOINT="$GUAC_OPENID_AUTHORIZATION_ENDPOINT" \
  -e OPENID_JWKS_ENDPOINT="$GUAC_OPENID_JWKS_ENDPOINT" \
  -e OPENID_ISSUER="$GUAC_OPENID_ISSUER" \
  -e OPENID_REDIRECT_URI="$GUAC_OPENID_REDIRECT_URI" \
  -e OPENID_USERNAME_CLAIM_TYPE="$GUAC_OPENID_USERNAME_CLAIM_TYPE" \
  -e OPENID_GROUPS_CLAIM_TYPE="$GUAC_OPENID_GROUPS_CLAIM_TYPE" \
  -e OPENID_SCOPE="$GUAC_OPENID_SCOPE" \
  -e OPENID_MAX_TOKEN_VALIDITY="$GUAC_OPENID_MAX_TOKEN_VALIDITY" \
  -e AUDIENCE="$API_CLIENT_ID" \
  -e ISSUER="$GUAC_OPENID_ISSUER" \
  microsoft/azuretre/guacamole-server:latest
