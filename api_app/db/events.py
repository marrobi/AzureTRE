import asyncio
from azure.mgmt.cosmosdb import CosmosDBManagementClient

from core.config import SUBSCRIPTION_ID, RESOURCE_GROUP_NAME, RESOURCE_LOCATION, COSMOSDB_ACCOUNT_NAME, STATE_STORE_DATABASE, STATE_STORE_RESOURCES_CONTAINER, STATE_STORE_RESOURCE_TEMPLATES_CONTAINER, STATE_STORE_RESOURCES_HISTORY_CONTAINER, STATE_STORE_OPERATIONS_CONTAINER, STATE_STORE_AIRLOCK_REQUESTS_CONTAINER, STATE_STORE_COSTS_CONTAINER
from core.credentials import get_credential
from services.logging import logger


async def bootstrap_database() -> bool:
    try:
        credential = get_credential()
        db_mgmt_client = CosmosDBManagementClient(credential=credential, subscription_id=SUBSCRIPTION_ID)

        await asyncio.gather(
            create_container_if_not_exists(db_mgmt_client, STATE_STORE_RESOURCES_CONTAINER, "/id"),
            create_container_if_not_exists(db_mgmt_client, STATE_STORE_RESOURCE_TEMPLATES_CONTAINER, "/id"),
            create_container_if_not_exists(db_mgmt_client, STATE_STORE_RESOURCES_HISTORY_CONTAINER, "/resourceId"),
            create_container_if_not_exists(db_mgmt_client, STATE_STORE_OPERATIONS_CONTAINER, "/id"),
            create_container_if_not_exists(db_mgmt_client, STATE_STORE_AIRLOCK_REQUESTS_CONTAINER, "/id"),
            # Cost day documents hold a large "rows" array that is only ever read, never filtered
            # on, so indexing it would multiply write RU and index storage for no benefit.
            create_container_if_not_exists(
                db_mgmt_client, STATE_STORE_COSTS_CONTAINER, "/partitionKey",
                excluded_paths=["/rows/*"])
        )

        return True

    except Exception as e:
        logger.exception("Could not bootstrap database")
        logger.debug(e)
        return False


async def create_container_if_not_exists(db_mgmt_client, container, partition_key, excluded_paths=None):

    resource = {
        "id": container,
        "partition_key": {
            "paths": [
                partition_key
            ],
            "kind": "Hash"
        }
    }

    if excluded_paths:
        resource["indexing_policy"] = {
            "indexing_mode": "consistent",
            "automatic": True,
            "included_paths": [{"path": "/*"}],
            "excluded_paths": [{"path": path} for path in excluded_paths] + [{"path": "/\"_etag\"/?"}]
        }

    def create_and_wait():
        poller = db_mgmt_client.sql_resources.begin_create_update_sql_container(
            resource_group_name=RESOURCE_GROUP_NAME,
            account_name=COSMOSDB_ACCOUNT_NAME,
            database_name=STATE_STORE_DATABASE,
            container_name=container,
            create_update_sql_container_parameters={
                "location": RESOURCE_LOCATION,
                "resource": resource
            }
        )
        # ARM accepts the request before the container exists, so wait for the operation to finish;
        # otherwise startup completes (and requests are served) while a container is still being
        # created, and any failure of the operation is never surfaced.
        poller.result()

    # the management SDK is synchronous, so keep the wait off the event loop
    await asyncio.to_thread(create_and_wait)
