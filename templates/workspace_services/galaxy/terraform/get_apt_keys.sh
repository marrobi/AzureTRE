#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Remove key if it already exists
sudo rm -f /etc/apt/trusted.gpg.d/docker-archive-keyring.gpg || true

# Get Docker Public key from Nexus
curl -fsSL "${NEXUS_PROXY_URL}"/repository/docker-public-key/gpg | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/docker-archive-keyring.gpg
