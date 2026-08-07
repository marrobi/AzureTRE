from unittest.mock import AsyncMock, MagicMock, patch
from azure.core.exceptions import AzureError
import pytest
from db import events

pytestmark = pytest.mark.asyncio


@patch("db.events.get_credential")
@patch("db.events.CosmosDBManagementClient")
async def test_bootstrap_database_success(cosmos_db_mgmt_client_mock, get_credential_async_context_mock):
    get_credential_async_context_mock.return_value = AsyncMock()
    cosmos_db_mgmt_client_mock.return_value = MagicMock()

    result = await events.bootstrap_database()

    assert result is True


@patch("db.events.get_credential")
@patch("db.events.CosmosDBManagementClient")
async def test_bootstrap_database_failure(cosmos_db_mgmt_client_mock, get_credential_async_context_mock):
    get_credential_async_context_mock.return_value = AsyncMock()
    cosmos_db_mgmt_client_mock.side_effect = AzureError("some error")

    result = await events.bootstrap_database()

    assert result is False


@patch("db.events.get_credential")
@patch("db.events.CosmosDBManagementClient")
async def test_bootstrap_database_waits_for_each_container_to_be_created(
        cosmos_db_mgmt_client_mock, get_credential_async_context_mock):
    # ARM accepts the create before the container exists, so bootstrap must await the poller -
    # otherwise the API starts serving requests against a container that isn't there yet.
    get_credential_async_context_mock.return_value = AsyncMock()
    client = MagicMock()
    cosmos_db_mgmt_client_mock.return_value = client

    result = await events.bootstrap_database()

    assert result is True
    pollers = client.sql_resources.begin_create_update_sql_container.return_value
    assert pollers.result.call_count == client.sql_resources.begin_create_update_sql_container.call_count


@patch("db.events.get_credential")
@patch("db.events.CosmosDBManagementClient")
async def test_bootstrap_database_reports_failure_when_a_container_operation_fails(
        cosmos_db_mgmt_client_mock, get_credential_async_context_mock):
    get_credential_async_context_mock.return_value = AsyncMock()
    client = MagicMock()
    client.sql_resources.begin_create_update_sql_container.return_value.result.side_effect = AzureError("nope")
    cosmos_db_mgmt_client_mock.return_value = client

    result = await events.bootstrap_database()

    assert result is False
