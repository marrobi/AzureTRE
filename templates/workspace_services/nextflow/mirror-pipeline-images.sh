#!/usr/bin/env bash
# Copies the container images that built-in pipelines need from public registries into the TRE container
# registry, as <registry>/mirror/<source image>. Batch nodes can only pull from Docker Hub (through Nexus)
# and the TRE registry. Run it as a TRE administrator after deploying or upgrading the service bundle.
# Usage: ./mirror-pipeline-images.sh <acr-name>
set -o errexit -o nounset -o pipefail

acr="${1:?Usage: $0 <acr-name>}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for list in "${here}"/app/pipelines/*/images.txt; do
  grep -vE '^\s*(#|$)' "${list}" | while read -r image; do
    echo "Importing ${image} as mirror/${image}"
    az acr import --name "${acr}" --source "${image}" --image "mirror/${image}" --force --output none
  done
done
