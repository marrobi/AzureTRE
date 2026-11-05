#!/bin/bash
# Packages the demo pipeline as a single zip for an Airlock import request.
# Usage: ./make-pipeline-zip.sh [output.zip]
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="$(realpath -m "${1:-gbr-population-compare.zip}")"

rm -f "${out}"
(cd "${here}" && zip -qr "${out}" gbr-population-compare -x '*/__pycache__/*' '*.pyc')
echo "Created ${out}"
unzip -l "${out}"
