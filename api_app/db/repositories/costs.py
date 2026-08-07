import asyncio
import hashlib
import json
from datetime import datetime, UTC
from typing import List

from core import config
from db.repositories.base import BaseRepository
from models.domain.costs import CostItemType, PersistedCostDay


class CostsRepository(BaseRepository):
    """Repository for the durable, API-owned cost collection (one document per collected day)."""

    # Cosmos caps a transactional batch at 100 operations and 2MB. A month of days for one scope
    # is normally well inside both, but a large TRE's daily row counts can approach the size cap,
    # so leave headroom for request overhead rather than writing right up to the limit.
    MAX_BATCH_OPERATIONS: int = 100
    MAX_BATCH_BYTES: int = 1_500_000

    @classmethod
    async def create(cls):
        cls = CostsRepository()
        await super().create(config.STATE_STORE_COSTS_CONTAINER)
        return cls

    @staticmethod
    def build_id(tre_id: str, scope: str, tag_name: str, tag_value: str, usage_date: str) -> str:
        """Deterministic id for a scope's day so repeated refreshes overwrite rather than duplicate."""
        key = f"{tre_id}|{scope}|{tag_name}|{tag_value}|{usage_date}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    @staticmethod
    def build_partition_key(tre_id: str, usage_date: str) -> str:
        """Partition by tre_id + year-month so a month's days stay within a single partition."""
        return f"{tre_id}/{usage_date[:7]}"

    @staticmethod
    def month_partition_keys(tre_id: str, from_date: str, to_date: str) -> List[str]:
        """Partition keys covering the (inclusive) day range, so reads stay partition-scoped."""
        keys = []
        year, month = int(from_date[:4]), int(from_date[5:7])
        last_year, last_month = int(to_date[:4]), int(to_date[5:7])
        while (year, month) <= (last_year, last_month):
            keys.append(f"{tre_id}/{year:04d}-{month:02d}")
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return keys

    async def get_cost_days(self, tre_id: str, scope: str, tag_name: str, tag_value: str,
                            from_date: str, to_date: str) -> List[PersistedCostDay]:
        """Return the collected days for a scope within the inclusive day range.

        One query per month partition, run concurrently, so every read is single-partition
        rather than a cross-partition scan.
        """
        query = (
            "SELECT * FROM c WHERE c.itemType = @itemType AND c.scope = @scope "
            "AND c.tag_name = @tagName AND c.tag_value = @tagValue "
            "AND c.usage_date >= @fromDate AND c.usage_date <= @toDate"
        )
        parameters = [
            {'name': '@itemType', 'value': CostItemType.cost_day},
            {'name': '@scope', 'value': scope},
            {'name': '@tagName', 'value': tag_name},
            {'name': '@tagValue', 'value': tag_value},
            {'name': '@fromDate', 'value': from_date},
            {'name': '@toDate', 'value': to_date},
        ]

        async def __read_partition(partition_key: str) -> List[PersistedCostDay]:
            items = self.container.query_items(
                query=query, parameters=parameters, partition_key=partition_key)
            return [PersistedCostDay(**item) async for item in items]

        partitions = await asyncio.gather(
            *[__read_partition(key)
              for key in self.month_partition_keys(tre_id, from_date, to_date)])
        return [day for partition in partitions for day in partition]

    @staticmethod
    def build_cost_day(tre_id: str, scope: str, tag_name: str, tag_value: str,
                       usage_date: str, rows: List[list], final: bool) -> PersistedCostDay:
        return PersistedCostDay(
            id=CostsRepository.build_id(tre_id, scope, tag_name, tag_value, usage_date),
            partitionKey=CostsRepository.build_partition_key(tre_id, usage_date),
            itemType=CostItemType.cost_day,
            tre_id=tre_id,
            scope=scope,
            tag_name=tag_name,
            tag_value=tag_value,
            usage_date=usage_date,
            rows=rows,
            final=final,
            collected_at=datetime.now(UTC).isoformat(),
        )

    async def save_cost_days(self, days: List[PersistedCostDay]) -> None:
        """Upsert the days as transactional batches, one or more per partition.

        All days of a month share a partition key, so a month's collection for one scope is
        normally a single round trip instead of one write per day. Cosmos caps a batch at both
        100 operations and 2MB, so batches are closed on whichever limit is reached first.
        """
        by_partition: dict = {}
        for day in days:
            by_partition.setdefault(day.partitionKey, []).append(day)

        for partition_key, partition_days in by_partition.items():
            batch: list = []
            batch_bytes = 0
            for day in partition_days:
                item = day.dict()
                item_bytes = len(json.dumps(item))
                if batch and (len(batch) >= self.MAX_BATCH_OPERATIONS
                              or batch_bytes + item_bytes > self.MAX_BATCH_BYTES):
                    await self.container.execute_item_batch(
                        batch_operations=batch, partition_key=partition_key)
                    batch, batch_bytes = [], 0
                batch.append(("upsert", (item,)))
                batch_bytes += item_bytes
            if batch:
                await self.container.execute_item_batch(
                    batch_operations=batch, partition_key=partition_key)
