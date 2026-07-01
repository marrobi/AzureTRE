from unittest.mock import AsyncMock
import pytest
import pytest_asyncio
from mock import patch

from db.migrations.resources import ResourceMigration


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def resource_migration():
    with patch('api.dependencies.database.Database.get_container_proxy', return_value=None):
        resource_migration = await ResourceMigration().create()
        yield resource_migration


async def test_add_unique_identifier_suffix_field_sets_last_4_chars(resource_migration):
    resource = {"id": "abc000d3-82da-4bfc-b6e9-9a7853ef753e", "properties": {}}
    resource_migration.query = AsyncMock(return_value=[resource])
    resource_migration.update_item_dict = AsyncMock()

    num_updated = await resource_migration.add_unique_identifier_suffix_field()

    assert num_updated == 1
    resource_migration.update_item_dict.assert_called_once()
    updated = resource_migration.update_item_dict.call_args[0][0]
    assert updated["properties"]["unique_identifier_suffix"] == "753e"


async def test_add_unique_identifier_suffix_field_creates_properties_when_missing(resource_migration):
    resource = {"id": "abc000d3-82da-4bfc-b6e9-9a7853ef753e"}
    resource_migration.query = AsyncMock(return_value=[resource])
    resource_migration.update_item_dict = AsyncMock()

    num_updated = await resource_migration.add_unique_identifier_suffix_field()

    assert num_updated == 1
    updated = resource_migration.update_item_dict.call_args[0][0]
    assert updated["properties"]["unique_identifier_suffix"] == "753e"


async def test_add_unique_identifier_suffix_field_no_resources(resource_migration):
    resource_migration.query = AsyncMock(return_value=[])
    resource_migration.update_item_dict = AsyncMock()

    num_updated = await resource_migration.add_unique_identifier_suffix_field()

    assert num_updated == 0
    resource_migration.update_item_dict.assert_not_called()
