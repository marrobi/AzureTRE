from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from mock import patch

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from db.repositories.costs import CostsRepository
from models.domain.costs import CostItemType, GranularityEnum


@pytest_asyncio.fixture
async def costs_repo():
    with patch('api.dependencies.database.Database.get_container_proxy', return_value=None):
        costs_repo = await CostsRepository.create()
        costs_repo._container = MagicMock()
        yield costs_repo


def test_build_id_is_deterministic():
    args = ("tre1", "/subscriptions/sub1", "tre_id", "tre1", GranularityEnum.daily, "2022-05-01", "2022-05-31")
    assert CostsRepository.build_id(*args) == CostsRepository.build_id(*args)


def test_build_id_differs_for_different_periods():
    id1 = CostsRepository.build_id("tre1", "s", "tre_id", "tre1", GranularityEnum.daily, "2022-05-01", "2022-05-31")
    id2 = CostsRepository.build_id("tre1", "s", "tre_id", "tre1", GranularityEnum.daily, "2022-06-01", "2022-06-30")
    assert id1 != id2


def test_build_partition_key_uses_year_month():
    assert CostsRepository.build_partition_key("tre1", GranularityEnum.daily, "2022-05-14") == "tre1/Daily/2022-05"


def test_build_partition_key_month_to_date_when_no_from_date():
    assert CostsRepository.build_partition_key("tre1", GranularityEnum.none, None) == "tre1/None/month-to-date"


@pytest.mark.asyncio
async def test_get_cost_query_result_returns_none_when_missing(costs_repo):
    costs_repo.container.read_item = AsyncMock(side_effect=CosmosResourceNotFoundError(message="not found"))
    result = await costs_repo.get_cost_query_result(
        "tre1", "/subscriptions/sub1", "tre_id", "tre1", GranularityEnum.daily, "2022-05-01", "2022-05-31")
    assert result is None


@pytest.mark.asyncio
async def test_save_cost_query_result_upserts_document(costs_repo):
    costs_repo.container.upsert_item = AsyncMock(return_value=None)
    saved = await costs_repo.save_cost_query_result(
        tre_id="tre1", scope="/subscriptions/sub1", tag_name="tre_id", tag_value="tre1",
        granularity=GranularityEnum.daily, from_date="2022-05-01", to_date="2022-05-31",
        resource_groups=["rg-tre1"], columns=[{"name": "PreTaxCost", "type": "Number"}],
        rows=[[1.0, 20220501, "rg-tre1", '"tre_id":"tre1"', "USD"]], final=True)

    costs_repo.container.upsert_item.assert_awaited_once()
    assert saved.itemType == CostItemType.cost_query_result
    assert saved.final is True
    assert saved.partitionKey == "tre1/Daily/2022-05"
    # id must be deterministic for the same period so refreshes overwrite rather than duplicate
    assert saved.id == CostsRepository.build_id(
        "tre1", "/subscriptions/sub1", "tre_id", "tre1", GranularityEnum.daily, "2022-05-01", "2022-05-31")
