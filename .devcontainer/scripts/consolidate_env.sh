#!/bin/bash
set -o errexit
set -o pipefail
set -o nounset
# Uncomment this line to see each command for debugging (careful: this will show secrets!)
# set -o xtrace

# usage: consolidate_env.sh [workdir] [file]

WORKDIR=${1:-"automatic"}
FILE=${2:-"automatic"}

# YQ query to get leaf keys
GET_LEAF_KEYS=".. | select(. == \"*\") | {(path | .[-1]): .} "
# YQ query to uppercase keys
UPCASE_KEYS="with_entries(.key |= upcase)"
# YQ query to map yaml entries to the following format: key=value
# needed for later env export
FORMAT_TO_ENV_FILE="to_entries| map(.key + \"=\" +  .value)|.[]"

# Export as UPPERCASE keys to file
# shellcheck disable=SC2086
yq e "$GET_LEAF_KEYS|$UPCASE_KEYS| $FORMAT_TO_ENV_FILE" config.yaml > $FILE

# shellcheck disable=SC2086
cat $WORKDIR/core/private.env >> $FILE

# shellcheck source=/dev/null
source "$FILE"

# if using Cosmos DB emulator set the state store endpoint, account name and key
if [ -n "${COSMOSDB_EMULATOR:-}" ]; then
  echo -e "STATE_STORE_ENDPOINT=http://localhost:8081\n\
STATE_STORE_ACCOUNT_NAME=localhost\n\
STATE_STORE_KEY=C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==\n\
STATE_STORE_SSL_VERIFY=false" >> "$FILE"

  # Run Cosmos DB emulator
  docker compose -f "$WORKDIR/devops/emulators/docker-compose.yaml" up -d
fi

