#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Remove the default Ubuntu DEB822 sources file (Ubuntu 24.04+) so that
# only the Nexus-proxied sources configured by cloud-init apt module are used.
sudo rm -f /etc/apt/sources.list.d/ubuntu.sources || true

# Remove key if it already exists
sudo rm -f /etc/apt/trusted.gpg.d/docker-archive-keyring.gpg || true

# Get Docker Public key from Nexus
curl -fsSL "${NEXUS_PROXY_URL}"/repository/docker-public-key/gpg | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/docker-archive-keyring.gpg
