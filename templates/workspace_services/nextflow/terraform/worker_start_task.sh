#!/bin/bash
# Prepares a Nextflow worker node. Nodes have no internet access, so:
#  - Nextflow's azcopy comes from the runtime image, which the pool prefetches from the TRE ACR.
#  - Docker Hub images are pulled through the TRE Nexus proxy.
set -o errexit -o nounset -o pipefail

mkdir -p "$AZ_BATCH_NODE_SHARED_DIR/bin"
cid=$(docker create "$NF_RUNTIME_IMAGE")
docker cp "$cid:/usr/local/bin/azcopy" "$AZ_BATCH_NODE_SHARED_DIR/bin/azcopy"
docker rm "$cid" >/dev/null
chmod 755 "$AZ_BATCH_NODE_SHARED_DIR/bin/azcopy"

python3 - <<'PY'
import json, os, pathlib
path = pathlib.Path("/etc/docker/daemon.json")
config = json.loads(path.read_text()) if path.exists() and path.read_text().strip() else {}
mirror = os.environ["NF_NEXUS_URL"] + ":8083"
if mirror not in config.get("registry-mirrors", []):
    config["registry-mirrors"] = [mirror] + config.get("registry-mirrors", [])
    path.write_text(json.dumps(config, indent=2))
PY
systemctl restart docker
echo "Worker node ready"
