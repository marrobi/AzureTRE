#!/bin/bash

ENABLE_EMULATOR=$1
export ACCEPT_EULA=$2
export CONFIG_PATH=$3

SQL_PASSWORD=$(openssl rand -base64 12)
export SQL_PASSWORD

if [ "$ENABLE_EMULATOR" != "true" ]; then
  echo "Emulator is not enabled. Exiting."
  exit 0
fi

if [ "$ACCEPT_EULA" != "true" ]; then
  echo "EULA is not accepted. Exiting."
  exit 0
else
  ACCEPT_EULA="Y"
fi

echo "Starting the Service Bus Emulator with the following configuration:"

SCRIPT_DIR=$(dirname "$0")
docker compose -f "$SCRIPT_DIR/docker-compose.yml" up -d

