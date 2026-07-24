import hashlib
from datetime import datetime, UTC
from typing import List, Optional

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from core import config
from db.repositories.base import BaseRepository
from models.domain.costs import CostItemType, GranularityEnum, PersistedCostQueryResult


class CostsRepository(BaseRepository):
    """Repository for the durable, API-owned cost collection (one document per split query period)."""

    @classmethod
    async def create(cls):
        cls = CostsRepository()
        await super().create(config.STATE_STORE_COSTS_CONTAINER)
        return cls

    @staticmethod
    def build_id(tre_id: str, scope: str, tag_name: str, tag_value: str,
                 granularity: GranularityEnum, from_date: Optional[str], to_date: Optional[str]) -> str:
        """Deterministic id for a period so repeated refreshes overwrite rather than duplicate."""
        key = f"{tre_id}|{scope}|{tag_name}|{tag_value}|{granularity}|{from_date}|{to_date}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    @staticmethod
    def build_partition_key(tre_id: str, granularity: GranularityEnum, from_date: Optional[str]) -> str:
        """Partition by tre_id + year-month so per-month reads stay within a single partition."""
        month = from_date[:7] if from_date else "month-to-date"
        return f"{tre_id}/{granularity}/{month}"

    async def get_cost_query_result(self, tre_id: str, scope: str, tag_name: str, tag_value: str,
                                    granularity: GranularityEnum, from_date: Optional[str],
                                    to_date: Optional[str]) -> Optional[PersistedCostQueryResult]:
        item_id = self.build_id(tre_id, scope, tag_name, tag_value, granularity, from_date, to_date)
        partition_key = self.build_partition_key(tre_id, granularity, from_date)
        try:
            item = await self.container.read_item(item=item_id, partition_key=partition_key)
        except CosmosResourceNotFoundError:
            return None
        return PersistedCostQueryResult(**item)

    async def save_cost_query_result(self, tre_id: str, scope: str, tag_name: str, tag_value: str,
                                     granularity: GranularityEnum, from_date: Optional[str], to_date: Optional[str],
                                     resource_groups: List[str], columns: List[dict], rows: List[list],
                                     final: bool) -> PersistedCostQueryResult:
        item = PersistedCostQueryResult(
            id=self.build_id(tre_id, scope, tag_name, tag_value, granularity, from_date, to_date),
            partitionKey=self.build_partition_key(tre_id, granularity, from_date),
            itemType=CostItemType.cost_query_result,
            tre_id=tre_id,
            scope=scope,
            tag_name=tag_name,
            tag_value=tag_value,
            granularity=granularity,
            from_date=from_date,
            to_date=to_date,
            resource_groups=resource_groups,
            columns=columns,
            rows=rows,
            final=final,
            collected_at=datetime.now(UTC).isoformat(),
        )
        await self.container.upsert_item(body=item.dict())
        return item
