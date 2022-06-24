#!/bin/bash

# Setup Script
set -euo pipefail

# Magic string for MSGraph
msGraphAppId="00000003-0000-0000-c000-000000000000"

function get_msgraph_scope() {
    oauthScope=$(az ad sp show --id ${msGraphAppId} --query "oauth2Permissions[?value=='$1'].id | [0]" --output tsv)
    jq -c . <<- JSON
    {
        "id": "${oauthScope}",
        "type": "Scope"
    }
JSON
}

function get_msgraph_role() {
    appRoleScope=$(az ad sp show --id ${msGraphAppId} --query "appRoles[?value=='$1'].id | [0]" --output tsv)
    jq -c . <<- JSON
    {
        "id": "${appRoleScope}",
        "type": "Role"
    }
JSON
}
