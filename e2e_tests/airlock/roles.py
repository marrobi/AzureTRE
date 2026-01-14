import logging
from httpx import AsyncClient, Timeout
from azure.identity import ClientSecretCredential
from e2e_tests.helpers import get_full_endpoint
from e2e_tests import cloud
import config

LOGGER = logging.getLogger(__name__)
TIMEOUT = Timeout(10, read=30)
GRAPH_URL = "https://graph.microsoft.com"


async def assign_airlock_manager_role(workspace_id: str, admin_token: str, verify: bool) -> None:
    """
    Assign the AirlockManager role to the test service principal for the given workspace.
    Uses Microsoft Graph API to assign the app role. Idempotent - handles already-assigned case.
    """
    async with AsyncClient(verify=verify, timeout=TIMEOUT) as client:
        # Get workspace to retrieve sp_id and airlock manager role ID
        response = await client.get(
            get_full_endpoint(f"/api/workspaces/{workspace_id}"),
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=TIMEOUT
        )
        if response.status_code != 200:
            LOGGER.error(f"Failed to get workspace: {response.status_code} - {response.text}")
            return

        workspace = response.json()["workspace"]
        sp_id = workspace["properties"].get("sp_id")
        airlock_role_id = workspace["properties"].get("app_role_id_workspace_airlock_manager")

        if not sp_id or not airlock_role_id:
            LOGGER.warning("Workspace does not have AirlockManager role configured, skipping")
            return

        # Get Graph API token
        credential = ClientSecretCredential(
            config.AAD_TENANT_ID,
            config.TEST_ACCOUNT_CLIENT_ID,
            config.TEST_ACCOUNT_CLIENT_SECRET,
            connection_verify=verify,
            authority=cloud.get_aad_authority_fqdn()
        )
        graph_token = credential.get_token("https://graph.microsoft.com/.default").token

        # Get the object ID of the test service principal
        response = await client.get(
            f"{GRAPH_URL}/v1.0/servicePrincipals?$filter=appId eq '{config.TEST_ACCOUNT_CLIENT_ID}'",
            headers={"Authorization": f"Bearer {graph_token}"},
            timeout=TIMEOUT
        )
        if response.status_code != 200 or not response.json().get("value"):
            LOGGER.error(f"Failed to get service principal: {response.status_code}")
            return

        principal_id = response.json()["value"][0]["id"]

        # Assign the role
        response = await client.post(
            f"{GRAPH_URL}/v1.0/servicePrincipals/{sp_id}/appRoleAssignedTo",
            headers={"Authorization": f"Bearer {graph_token}", "Content-Type": "application/json"},
            json={"principalId": principal_id, "resourceId": sp_id, "appRoleId": airlock_role_id},
            timeout=TIMEOUT
        )

        if response.status_code == 201:
            LOGGER.info(f"Assigned AirlockManager role to principal {principal_id}")
        elif response.status_code == 409 or "already exists" in response.text.lower():
            LOGGER.info(f"AirlockManager role already assigned to principal {principal_id}")
        else:
            LOGGER.warning(f"Failed to assign role: {response.status_code} - {response.text}")
