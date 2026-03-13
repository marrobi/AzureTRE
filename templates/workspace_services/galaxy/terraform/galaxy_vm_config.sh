#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Install Docker CE from Nexus-proxied apt repositories
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release jq
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Configure Docker to use Nexus as registry mirror
jq -n --arg proxy "${NEXUS_PROXY_URL}:8083" '{"registry-mirrors": [$proxy]}' | sudo tee /etc/docker/daemon.json
sudo systemctl daemon-reload
sudo systemctl enable docker
sudo systemctl restart docker

# Create Galaxy export directory with appropriate ownership for Galaxy container user (UID 1450)
mkdir -p /galaxy/export
chown -R 1450:1450 /galaxy
chmod -R 755 /galaxy

# Run bgruening/galaxy container with Docker-in-Docker support for interactive tools.
# --privileged is required to allow Galaxy to spawn sibling Docker containers
# for interactive tools (Jupyter, RStudio) via Docker-in-Docker.
# Port 80: nginx (single entry point - routes to gunicorn, reports, flower,
#          tusd, static files, and gx-it-proxy for interactive tools internally)
docker run -d \
  --name galaxy \
  --restart unless-stopped \
  --privileged \
  -p 80:80 \
  -v /galaxy/export:/export \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e NONUSE=proftp \
  -e GALAXY_CONFIG_INTERACTIVETOOLS_ENABLE=True \
  -e GALAXY_CONFIG_ALLOW_USER_CREATION=True \
  -e GALAXY_CONFIG_ALLOW_USER_DELETION=True \
  quay.io/bgruening/galaxy:${GALAXY_IMAGE_TAG}
