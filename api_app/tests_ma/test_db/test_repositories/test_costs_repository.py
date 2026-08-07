import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from mock import patch

from db.repositories.costs import CostsRepository
from models.domain.costs import CostItemType


@pytest_asyncio.fixture
async def costs_repo():
    with patch('api.dependencies.database.Database.get_container_proxy', return_value=None):
        costs_repo = await CostsRepository.create()
        costs_repo._container = MagicMock()
        yield costs_repo


def test_build_id_is_deterministic():
    args = ("tre1", "/subscriptions/sub1", "tre_id", "tre1", "2022-05-01")
    assert CostsRepository.build_id(*args) == CostsRepository.build_id(*args)


def test_build_id_differs_per_day():
    id1 = CostsRepository.build_id("tre1", "s", "tre_id", "tre1", "2022-05-01")
    id2 = CostsRepository.build_id("tre1", "s", "tre_id", "tre1", "2022-05-02")
    assert id1 != id2


def test_build_id_differs_per_scope():
    id1 = CostsRepository.build_id("tre1", "/subscriptions/sub1", "tre_id", "tre1", "2022-05-01")
    id2 = CostsRepository.build_id("tre1", "/subscriptions/sub2", "tre_id", "tre1", "2022-05-01")
    assert id1 != id2


def test_build_partition_key_uses_year_month():
    assert CostsRepository.build_partition_key("tre1", "2022-05-14") == "tre1/2022-05"


def test_month_partition_keys_covers_every_month_in_range():
    keys = CostsRepository.month_partition_keys("tre1", "2021-11-15", "2022-02-03")
    assert keys == ["tre1/2021-11", "tre1/2021-12", "tre1/2022-01", "tre1/2022-02"]


def test_month_partition_keys_single_month():
    assert CostsRepository.month_partition_keys("tre1", "2022-05-01", "2022-05-31") == ["tre1/2022-05"]


@pytest.mark.asyncio
async def test_get_cost_days_reads_each_month_partition_separately(costs_repo):
    queried = []

    def __query_items(**kwargs):
        queried.append(kwargs)

        async def __empty():
            return
            yield  # pragma: no cover - generator with no items
        return __empty()

    costs_repo.container.query_items = MagicMock(side_effect=__query_items)

    await costs_repo.get_cost_days(
        "tre1", "/subscriptions/sub1", "tre_id", "tre1", "2022-05-30", "2022-06-02")

    # one partition-scoped query per month the range spans, so reads never scan cross-partition
    assert [call["partition_key"] for call in queried] == ["tre1/2022-05", "tre1/2022-06"]
    parameters = {p["name"]: p["value"] for p in queried[0]["parameters"]}
    assert parameters["@fromDate"] == "2022-05-30"
    assert parameters["@toDate"] == "2022-06-02"


@pytest.mark.asyncio
async def test_save_cost_days_batches_per_month_partition(costs_repo):
    costs_repo.container.execute_item_batch = AsyncMock(return_value=None)

    days = [
        CostsRepository.build_cost_day(
            tre_id="tre1", scope="/subscriptions/sub1", tag_name="tre_id", tag_value="tre1",
            usage_date=usage_date, rows=[[1.0, 20220501, "rg-tre1", '"tre_id":"tre1"', "USD"]],
            final=True)
        for usage_date in ("2022-05-30", "2022-05-31", "2022-06-01")]

    await costs_repo.save_cost_days(days)

    # days of a month share a partition, so a month is written in a single round trip
    batched = costs_repo.container.execute_item_batch.await_args_list
    assert [call.kwargs["partition_key"] for call in batched] == ["tre1/2022-05", "tre1/2022-06"]
    assert len(batched[0].kwargs["batch_operations"]) == 2
    assert batched[0].kwargs["batch_operations"][0][0] == "upsert"


@pytest.mark.asyncio
async def test_save_cost_days_splits_batches_that_would_exceed_the_size_limit(costs_repo):
    costs_repo.container.execute_item_batch = AsyncMock(return_value=None)

    # a large TRE's daily row counts can push a month of days past Cosmos' 2MB batch limit,
    # so the writer must close a batch on size as well as on operation count
    big_rows = [[1.0, 20220501, "rg-tre1", '"tre_id":"tre1"', "USD"]] * 4000
    days = [
        CostsRepository.build_cost_day(
            tre_id="tre1", scope="/subscriptions/sub1", tag_name="tre_id", tag_value="tre1",
            usage_date=f"2022-05-{day:02d}", rows=big_rows, final=True)
        for day in range(1, 32)]

    await costs_repo.save_cost_days(days)

    batched = costs_repo.container.execute_item_batch.await_args_list
    assert len(batched) > 1
    assert all(call.kwargs["partition_key"] == "tre1/2022-05" for call in batched)
    # every day is still written exactly once
    assert sum(len(call.kwargs["batch_operations"]) for call in batched) == len(days)
    assert all(len(json.dumps([op[1][0] for op in call.kwargs["batch_operations"]]))
               <= CostsRepository.MAX_BATCH_BYTES for call in batched)


def test_build_cost_day_is_deterministic_and_partitioned_by_month():
    day = CostsRepository.build_cost_day(
        tre_id="tre1", scope="/subscriptions/sub1", tag_name="tre_id", tag_value="tre1",
        usage_date="2022-05-01", rows=[[1.0, 20220501, "rg-tre1", '"tre_id":"tre1"', "USD"]],
        final=True)

    assert day.itemType == CostItemType.cost_day
    assert day.final is True
    assert day.usage_date == "2022-05-01"
    assert day.partitionKey == "tre1/2022-05"
    # id must be deterministic for the same day so refreshes overwrite rather than duplicate
    assert day.id == CostsRepository.build_id(
        "tre1", "/subscriptions/sub1", "tre_id", "tre1", "2022-05-01")
