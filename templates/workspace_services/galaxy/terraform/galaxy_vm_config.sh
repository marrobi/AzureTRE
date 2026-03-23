#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Install Docker CE from Nexus-proxied apt repositories
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release jq
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo systemctl daemon-reload
sudo systemctl enable docker
sudo systemctl restart docker

# Login to ACR using VM managed identity via IMDS (bypasses firewall, uses private endpoint)
ACR_LOGIN_SERVER="${MGMT_ACR_NAME}.azurecr.io"
ACCESS_TOKEN=$(curl -s -H 'Metadata:true' "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/" | jq -r '.access_token')
ACR_REFRESH_TOKEN=$(curl -s -X POST "https://$${ACR_LOGIN_SERVER}/oauth2/exchange" -H "Content-Type: application/x-www-form-urlencoded" -d "grant_type=access_token&service=$${ACR_LOGIN_SERVER}&access_token=$${ACCESS_TOKEN}" | jq -r '.refresh_token')
echo "$${ACR_REFRESH_TOKEN}" | docker login "$${ACR_LOGIN_SERVER}" --username 00000000-0000-0000-0000-000000000000 --password-stdin

# Create Galaxy export directory with appropriate ownership for Galaxy container user (UID 1450)
mkdir -p /galaxy/export
chown -R 1450:1450 /galaxy
chmod -R 755 /galaxy

# Pull Galaxy image from ACR (imported during bundle build) and run container.
# --privileged is required to allow Galaxy to spawn sibling Docker containers
# for interactive tools (Jupyter, RStudio) via Docker-in-Docker.
# Port 80: nginx (single entry point - routes to gunicorn, reports, flower,
#          tusd, static files, and gx-it-proxy for interactive tools internally)
# Pull fixed Galaxy image from ACR (built during bundle build with psycopg2 fix)
GALAXY_IMAGE="$${ACR_LOGIN_SERVER}/microsoft/azuretre/galaxy-vm:${GALAXY_IMAGE_TAG}"
docker pull "$${GALAXY_IMAGE}"

# Pull the Jupyter notebook image from ACR (imported during bundle build)
# and retag it to the name Galaxy expects so it doesn't try to pull from quay.io.
JUPYTER_ACR_IMAGE="$${ACR_LOGIN_SERVER}/microsoft/azuretre/galaxy-jupyter-notebook:2021-03-05"
docker pull "$${JUPYTER_ACR_IMAGE}"
docker tag "$${JUPYTER_ACR_IMAGE}" quay.io/bgruening/docker-jupyter-notebook:2021-03-05

docker run -d \
  --name galaxy \
  --restart unless-stopped \
  --privileged \
  -p 80:80 \
  -v /galaxy/export:/export \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e NONUSE=proftp \
  -e GALAXY_CONFIG_INTERACTIVETOOLS_ENABLE=True \
  -e GALAXY_CONFIG_ALLOW_USER_DELETION=True \
  -e GALAXY_CONFIG_TOOL_DATA_TABLE_CONFIG_PATH=/galaxy/config/tool_data_table_conf.xml \
  -e GALAXY_CONFIG_SHED_TOOL_DATA_TABLE_CONFIG=/galaxy/config/tool_data_table_conf.xml \
  -e "GALAXY_CONFIG_GALAXY_INFRASTRUCTURE_URL=https://${GALAXY_HOSTNAME}" \
  -e "GALAXY_CONFIG_WELCOME_URL=/etc/galaxy/web/welcome.html" \
  -e GALAXY_CONFIG_ENABLE_OIDC=True \
  -e "GALAXY_OIDC_CLIENT_ID=${OIDC_CLIENT_ID}" \
  -e "GALAXY_OIDC_CLIENT_SECRET=${OIDC_CLIENT_SECRET}" \
  -e "GALAXY_OIDC_TENANT_ID=${OIDC_TENANT_ID}" \
  -e "GALAXY_OIDC_AUTHORITY_URL=${OIDC_AUTHORITY_URL}" \
  -e "GALAXY_HOSTNAME=${GALAXY_HOSTNAME}" \
  -e "GALAXY_CONFIG_ADMIN_USERS=${GALAXY_ADMIN_USERS}" \
  -e GALAXY_DESTINATIONS_DEFAULT=docker_dispatch \
  -e GALAXY_DESTINATIONS_DOCKER_DEFAULT=slurm_cluster_docker \
  "$${GALAXY_IMAGE}"
