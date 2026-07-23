from datetime import datetime, date, timedelta
import asyncio
from enum import Enum
from functools import lru_cache
from typing import Dict, List, Optional, Tuple, Union
import pandas as pd

from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import QueryGrouping, QueryAggregation, QueryDataset, QueryDefinition, \
    TimeframeType, ExportType, QueryTimePeriod, QueryFilter, QueryComparisonExpression, QueryResult, QueryColumn
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError

from azure.mgmt.resource import ResourceManagementClient

from core import config, credentials
from db.errors import EntityDoesNotExist
from db.repositories.costs import CostsRepository
from db.repositories.shared_services import SharedServiceRepository
from db.repositories.user_resources import UserResourceRepository
from db.repositories.workspace_services import WorkspaceServiceRepository
from db.repositories.workspaces import WorkspaceRepository
from models.domain.costs import GranularityEnum, CostReport, WorkspaceCostReport, CostItem, WorkspaceServiceCostItem, \
    CostRow
from models.domain.resource import Resource
from services.logging import logger


class ResultColumnDaily(Enum):
    Cost = 0
    Date = 1
    ResourceGroup = 2
    Tag = 3
    Currency = 4


class ResultColumn(Enum):
    Cost = 0
    ResourceGroup = 1
    Tag = 2
    Currency = 3


class WorkspaceDoesNotExist(Exception):
    """Raised when the workspace is not found by provided id"""


class SubscriptionNotSupported(Exception):
    """Raised when subscription does not support cost management"""


class TooManyRequests(Exception):
    """Raised when cost management api is being throttled, retry after given number of seconds"""
    retry_after: int

    def __init__(self, retry_after: int, *args: object) -> None:
        super().__init__(*args)
        self.retry_after = retry_after


class ServiceUnavailable(Exception):
    """Raised when cost management is unavaiable, retry after given number of seconds"""
    retry_after: int

    def __init__(self, retry_after: int, *args: object) -> None:
        super().__init__(*args)
        self.retry_after = retry_after


class CostCacheItem():
    """Holds cost qery result and time to leave for storing in cache"""
    result: QueryResult
    ttl: datetime

    def __init__(self, item: QueryResult, ttl: datetime) -> None:
        self.result = item
        self.ttl = ttl


# make sure CostService is singleton
@lru_cache(maxsize=None)
class CostService:
    scope: str
    client: CostManagementClient
    cache: Dict[str, CostCacheItem]
    TRE_ID_TAG: str = "tre_id"
    TRE_CORE_SERVICE_ID_TAG: str = "tre_core_service_id"
    TRE_WORKSPACE_ID_TAG: str = "tre_workspace_id"
    TRE_SHARED_SERVICE_ID_TAG: str = "tre_shared_service_id"
    TRE_WORKSPACE_SERVICE_ID_TAG: str = "tre_workspace_service_id"
    TRE_USER_RESOURCE_ID_TAG: str = "tre_user_resource_id"
    TRE_UNTAGGED: str = ""
    RATE_LIMIT_RETRY_AFTER_HEADER_KEY: str = "x-ms-ratelimit-microsoft.costmanagement-entity-retry-after"
    SERVICE_UNAVAILABLE_RETRY_AFTER_HEADER_KEY: str = "Retry-After"
    # Cost Management rejects custom periods longer than a year, so longer reports are split.
    MAX_QUERY_PERIOD: timedelta = timedelta(days=364)
    CACHE_TTL: timedelta = timedelta(hours=2)
    # Azure keeps re-rating the most recent days for a short window, so a period is only treated
    # as final (frozen in the collection and never re-queried) once its last day is at least this
    # many days in the past - otherwise idempotent refresh could freeze still-settling data.
    COST_DATA_SETTLING_DAYS: int = 4
    # Cap how many live Cost Management queries run concurrently: month-aligned splitting can
    # produce many sub-periods for a long cold range, and Cost Management throttles bursts.
    LIVE_QUERY_CONCURRENCY: int = 4

    def __init__(self) -> None:
        self.scope = "/subscriptions/{}".format(config.SUBSCRIPTION_ID)
        self.client = CostManagementClient(credential=credentials.get_credential())
        self.__resource_clients = {}
        self.get_resource_management_client(config.SUBSCRIPTION_ID)
        self.cache = {}

    def get_resource_management_client(self, subscription_id: Optional[str] = None) -> ResourceManagementClient:
        if subscription_id is None:
            subscription_id = config.SUBSCRIPTION_ID

        # Check if resource client is already created for the subscription
        if subscription_id not in self.__resource_clients.keys():
            self.__resource_clients[subscription_id] = ResourceManagementClient(
                credentials.get_credential(),
                subscription_id,
                base_url=config.RESOURCE_MANAGER_ENDPOINT,
                credential_scopes=config.CREDENTIAL_SCOPES
            )
        return self.__resource_clients[subscription_id]

    def get_cached_result(self, key: str) -> Union[QueryResult, None]:
        """Returns cached item result.

        Args:
            key (str): key of the cached item in cache.
        Returns:
            result (Union[QueryResult, None]): cost query result or None if not found or expired.
        """
        cached_item: CostCacheItem = self.cache.get(key, None)

        # return None if key doesn't exist
        if cached_item is None:
            return None

        # return None if key expired
        if (datetime.now() > cached_item.ttl):
            # remove expired cache item
            self.cache.pop(key)
            return None

        return cached_item.result

    def clear_expired_cache_items(self) -> None:
        """Clears all expired cache items."""
        expired_keys = [key for key in self.cache.keys() if datetime.now() > self.cache[key].ttl]
        for key in expired_keys:
            self.cache.pop(key)

    def cache_result(self, key: str, result: QueryResult, timedelta: timedelta) -> None:
        """Add cost result to cache.

        Args:
            key (str) : key of the cached item in cache.
            result (QueryResult) : cost query result to cache.
        """
        self.cache[key] = CostCacheItem(result, datetime.now() + timedelta)
        self.clear_expired_cache_items()

    async def query_tre_costs(self, tre_id, granularity: GranularityEnum, from_date: datetime, to_date: datetime,
                              workspace_repo: WorkspaceRepository,
                              shared_services_repo: SharedServiceRepository,
                              costs_repo: Optional[CostsRepository] = None) -> CostReport:

        subscription_ids = {config.SUBSCRIPTION_ID}

        #  get all subscription ids from the workspace objects
        subscription_ids.update(await self.__get_workspace_subscription_ids(workspace_repo))

        #  loop through all subscription ids and get resource groups and costs
        resource_groups_dict = {}
        summarized_result = []
        for subscription_id in subscription_ids:
            resource_groups_dict[subscription_id] = self.get_resource_groups_by_tag(self.TRE_ID_TAG, tre_id, subscription_id)

            query_result = await self.query_costs(CostService.TRE_ID_TAG, tre_id, granularity, from_date, to_date, list(resource_groups_dict[subscription_id].keys()), subscription_id, costs_repo)

            #  append the result to the summarized result
            summarized_result.extend(self.summarize_untagged(query_result, granularity, resource_groups_dict[subscription_id]))

        query_result_dict = self.__query_result_to_dict(summarized_result, granularity)

        cost_report = CostReport(core_services=[], shared_services=[], workspaces=[])

        cost_report.core_services = self.__extract_cost_rows_by_tag(
            granularity, query_result_dict, CostService.TRE_CORE_SERVICE_ID_TAG, tre_id)

        cost_report.shared_services = await self.__get_shared_services_costs(
            granularity, query_result_dict, shared_services_repo)

        cost_report.workspaces = await self.__get_workspaces_costs(granularity, query_result_dict, workspace_repo)

        return cost_report

    async def __get_workspace_subscription_ids(self, workspace_repo: WorkspaceRepository) -> list:
        #  we currently have to query ALL workspace resources to get the subscription ids to calculate costs for
        #  this may be able to change if we store subscriptions in config as per this issue: https://github.com/microsoft/AzureTRE/issues/4528
        workspaces = await workspace_repo.get_active_workspaces()
        subscription_ids = []
        for workspace in workspaces:
            #  check if the property exists and is not empty
            if not workspace.properties.get("workspace_subscription_id"):
                continue
            #  add the subscription id to the set
            subscription_id = workspace.properties["workspace_subscription_id"]
            if subscription_id not in subscription_ids:
                subscription_ids.append(subscription_id)
        return subscription_ids

    async def query_tre_workspace_costs(self, workspace_id: str, granularity: GranularityEnum, from_date: Optional[datetime],
                                        to_date: Optional[datetime],
                                        workspace_repo: WorkspaceRepository,
                                        workspace_services_repo: WorkspaceServiceRepository,
                                        user_resource_repo,
                                        costs_repo: Optional[CostsRepository] = None) -> WorkspaceCostReport:

        resource_groups_dict = self.get_resource_groups_by_tag(self.TRE_WORKSPACE_ID_TAG, workspace_id)

        subscription_id = None

        #  if no resource groups are found with the tag, they may be in another subscription
        #  so we need to get the workspace subscription id and query the resource groups again
        if not resource_groups_dict:
            try:
                workspace = await workspace_repo.get_workspace_by_id(workspace_id)
                subscription_id = workspace.properties["workspace_subscription_id"]
                resource_groups_dict = self.get_resource_groups_by_tag(self.TRE_WORKSPACE_ID_TAG, workspace_id, subscription_id)

            except EntityDoesNotExist:
                raise WorkspaceDoesNotExist(f"workspace_id [{workspace_id}] does not exist")

        query_result = await self.query_costs(CostService.TRE_WORKSPACE_ID_TAG, workspace_id, granularity, from_date, to_date, list(resource_groups_dict.keys()), subscription_id, costs_repo)

        summarized_result = self.summarize_untagged(query_result, granularity, resource_groups_dict)
        query_result_dict = self.__query_result_to_dict(summarized_result, granularity)

        try:
            #  check if workspace is already loaded
            if 'workspace' not in locals() or workspace is None:
                workspace = await workspace_repo.get_workspace_by_id(workspace_id)
            workspace_cost_report: WorkspaceCostReport = WorkspaceCostReport(
                id=workspace_id,
                name=self.__get_resource_name(workspace),
                costs=self.__extract_cost_rows_by_tag(granularity, query_result_dict, CostService.TRE_WORKSPACE_ID_TAG,
                                                      workspace_id),
                workspace_services=await self.__get_workspace_services_costs(granularity, query_result_dict,
                                                                             workspace_services_repo,
                                                                             user_resource_repo,
                                                                             workspace_id))

            return workspace_cost_report
        except EntityDoesNotExist:
            raise WorkspaceDoesNotExist(f"workspace_id [{workspace_id}] does not exist")

    def extract_resource_group_tag(self, tags):
        if self.TRE_WORKSPACE_ID_TAG in tags:
            return f'"{self.TRE_WORKSPACE_ID_TAG}":"{tags[self.TRE_WORKSPACE_ID_TAG]}"'
        else:
            return f'"{self.TRE_ID_TAG}":"{tags[self.TRE_ID_TAG]}"'

    def get_resource_groups_by_tag(self, tag_name, tag_value, subscription_id: Optional[str] = None) -> dict:

        resource_client = self.get_resource_management_client(subscription_id)
        resource_groups = resource_client.resource_groups.list(filter=f"tagName eq '{tag_name}' and tagValue eq '{tag_value}'")

        return {resouce_group.name: self.extract_resource_group_tag(resouce_group.tags) for resouce_group in resource_groups}

    def summarize_untagged(self, query_result: QueryResult, granularity: GranularityEnum, resource_groups_dict: dict) -> list:
        if len(query_result.rows) == 0:
            return []

        # convert to pandas DataFrame
        df = pd.DataFrame.from_records(query_result.rows)
        columns = []
        for i in range(len(query_result.columns)):
            columns.append(query_result.columns[i].name)
        df.columns = columns

        # fill tags for untagged
        untagged_resource_groups = list(df.loc[df["Tag"] == "", "ResourceGroup"].unique())
        for rg in untagged_resource_groups:
            df.loc[(df["Tag"] == "") & (df["ResourceGroup"] == rg), "Tag"] = resource_groups_dict[rg]

        # group by
        if granularity == GranularityEnum.none:
            c = ["ResourceGroup", "Tag", "Currency"]
        else:
            c = ["UsageDate", "ResourceGroup", "Tag", "Currency"]

        df = df.groupby(c).agg({'PreTaxCost': 'sum'})

        # reset index and reorder columns
        df.reset_index(inplace=True)
        c.insert(0, "PreTaxCost")
        df = df[c]

        # convert to list of rows
        return df.values.tolist()

    def __get_resource_name(self, resource: Resource):
        key = "display_name"
        if key in resource.properties.keys():
            return resource.properties[key]
        else:
            return resource.templateName

    def __extract_cost_item(self, resource: Resource, granularity: GranularityEnum, query_result_dict: dict, tag: str):
        return CostItem(
            id=resource.id,
            name=self.__get_resource_name(resource),
            costs=self.__extract_cost_rows_by_tag(granularity, query_result_dict, tag, resource.id)
        )

    async def __get_workspaces_costs(self, granularity, query_result_dict, workspace_repo):
        return [self.__extract_cost_item(workspace, granularity, query_result_dict, CostService.TRE_WORKSPACE_ID_TAG)
                for workspace in await workspace_repo.get_active_workspaces()]

    async def __get_shared_services_costs(self, granularity, query_result_dict, shared_services_repo):
        return [self.__extract_cost_item(shared_service, granularity, query_result_dict,
                                         CostService.TRE_SHARED_SERVICE_ID_TAG)
                for shared_service in await shared_services_repo.get_active_shared_services()]

    async def __get_workspace_services_costs(self, granularity, query_result_dict,
                                             workspace_services_repo: WorkspaceServiceRepository,
                                             user_resource_repo: UserResourceRepository, workspace_id: str):
        workspace_services_costs = []
        workspace_services_list = await workspace_services_repo.get_active_workspace_services_for_workspace(workspace_id)
        for workspace_service in workspace_services_list:
            workspace_service_cost_item = WorkspaceServiceCostItem(
                id=workspace_service.id,
                name=self.__get_resource_name(workspace_service),
                costs=self.__extract_cost_rows_by_tag(granularity, query_result_dict,
                                                      CostService.TRE_WORKSPACE_SERVICE_ID_TAG,
                                                      workspace_service.id),
                user_resources=[]
            )

            workspace_service_cost_item.user_resources = [self.__extract_cost_item(user_resource,
                                                                                   granularity,
                                                                                   query_result_dict,
                                                                                   CostService.TRE_USER_RESOURCE_ID_TAG)
                                                          for user_resource in
                                                          await user_resource_repo.get_user_resources_for_workspace_service(
                                                              workspace_id,
                                                              workspace_service.id)]

            workspace_services_costs.append(workspace_service_cost_item)
        return workspace_services_costs

    def __create_cost_row(self, cost, currency: str, cost_date: date):
        return CostRow(cost=cost, currency=currency, date=cost_date)

    def __extract_cost_rows_by_tag(self, granularity, query_result_dict, tag_name, tag_value):
        cost_rows = []
        cost_key = f'"{tag_name}":"{tag_value}"'
        if cost_key in query_result_dict.keys():
            costs = query_result_dict[cost_key]
            if granularity == GranularityEnum.none:
                cost_rows = [
                    self.__create_cost_row(cost[ResultColumn.Cost.value],
                                           cost[ResultColumn.Currency.value], None) for cost in costs]
            else:
                cost_rows = [
                    self.__create_cost_row(cost[ResultColumnDaily.Cost.value],
                                           cost[ResultColumnDaily.Currency.value],
                                           self.__parse_cost_management_date_value(
                                               cost[ResultColumnDaily.Date.value])) for cost in costs]

        return cost_rows

    def split_query_period(self, from_date: Optional[datetime], to_date: Optional[datetime]) -> List[Tuple[Optional[datetime], Optional[datetime]]]:
        """Split a report period into calendar-month-aligned sub-periods (see #2350).

        Aligning to whole months means read reports share the same period keys as the
        month-aligned data the Cost Processor persists (the current/previous-month refresh and
        the history backfill), so once a month is in the collection every report reuses it
        instead of re-querying Azure. Interior sub-periods are always whole calendar months
        (stable, reusable keys); the first and last may be partial when the requested range does
        not start or end on a month boundary. Whole months are also always well within Cost
        Management's one-year-per-query limit."""
        # month to date report - no custom period, single query
        if from_date is None or to_date is None:
            return [(from_date, to_date)]

        periods = []
        period_start = from_date
        while period_start <= to_date:
            # a sub-period never crosses a month boundary, so it lines up with stored month data
            period_end = min(self.__end_of_month(period_start), to_date)
            periods.append((period_start, period_end))
            # next period starts the following day to avoid double-counting
            period_start = period_end + timedelta(days=1)
        return periods

    @staticmethod
    def __end_of_month(value: datetime) -> datetime:
        first_of_next_month = (value.replace(day=1) + timedelta(days=32)).replace(day=1)
        return first_of_next_month - timedelta(days=1)

    def build_query_cache_key(self, tag_name: str, tag_value: str, granularity: GranularityEnum,
                              from_date: Optional[datetime], to_date: Optional[datetime],
                              resource_groups: list, scope: str) -> str:
        return (f"{tag_name}_{tag_value}_granularity{granularity}"
                f"_from_date{from_date}_to_date{to_date}"
                f"_scope{scope}_rgs{'_'.join(resource_groups)}")

    async def query_costs(self, tag_name: str, tag_value: str,
                          granularity: GranularityEnum, from_date: Optional[datetime],
                          to_date: Optional[datetime],
                          resource_groups: list,
                          subscription_id: Optional[str] = None,
                          costs_repo: Optional[CostsRepository] = None) -> QueryResult:

        scope = "/subscriptions/{}".format(subscription_id) if subscription_id else self.scope

        # Monthly reports are derived by aggregating the (cached) Daily data rather than
        # issuing a separate Cost Management query: this reuses the durable Daily collection,
        # keeps Monthly and Daily totals reconciled, and avoids extra Azure round-trips (#2350).
        if granularity == GranularityEnum.monthly:
            daily_result = await self.query_costs(
                tag_name, tag_value, GranularityEnum.daily, from_date, to_date,
                resource_groups, subscription_id, costs_repo)
            return self.__aggregate_daily_to_monthly(daily_result)

        periods = self.split_query_period(from_date, to_date)

        # First resolve each period from the in-memory cache or the durable collection.
        # These are cheap; anything still missing needs a live Cost Management query.
        resolved: List[Optional[QueryResult]] = []
        cache_keys: List[str] = []
        for period_from_date, period_to_date in periods:
            cache_key = self.build_query_cache_key(
                tag_name, tag_value, granularity, period_from_date, period_to_date, resource_groups, scope)
            cache_keys.append(cache_key)

            # 1) in-memory cache
            period_result = self.get_cached_result(cache_key)

            # 2) durable cost collection (finalised periods only)
            if period_result is None and costs_repo is not None:
                period_result = await self.__get_period_from_collection(
                    costs_repo, tag_name, tag_value, granularity, period_from_date, period_to_date, scope)
                if period_result is not None:
                    self.cache_result(cache_key, period_result, CostService.CACHE_TTL)
            resolved.append(period_result)

        # 3) Run the outstanding live Cost Management queries off the event loop and
        #    concurrently. The SDK client is synchronous, so calling it inline would block
        #    the event loop for the whole (often tens of seconds) query - long enough for the
        #    App Gateway health probe to fail and the backend to be marked unhealthy (see #2).
        #    to_thread keeps the loop responsive; gather also parallelises split sub-periods.
        live_indexes = [i for i, result in enumerate(resolved) if result is None]
        if live_indexes:
            # Bound how many live Cost Management queries run at once: month-aligned splitting can
            # produce many sub-periods for a long cold range, and Cost Management throttles bursts.
            semaphore = asyncio.Semaphore(CostService.LIVE_QUERY_CONCURRENCY)

            async def __run_live_query(index: int) -> QueryResult:
                async with semaphore:
                    return await asyncio.to_thread(
                        self.query_costs_period, tag_name, tag_value, granularity,
                        periods[index][0], periods[index][1], resource_groups, scope)

            live_results = await asyncio.gather(*[__run_live_query(i) for i in live_indexes])
            for i, period_result in zip(live_indexes, live_results):
                resolved[i] = period_result
                self.cache_result(cache_keys[i], period_result, CostService.CACHE_TTL)
                if costs_repo is not None:
                    await self.__persist_period(
                        costs_repo, tag_name, tag_value, granularity, periods[i][0], periods[i][1],
                        resource_groups, scope, period_result,
                        final=self.__is_period_final(periods[i][1]))

        merged_result: Optional[QueryResult] = None
        for period_result in resolved:
            if merged_result is None:
                # fresh QueryResult so cached period results are never mutated while merging
                merged_result = QueryResult(columns=period_result.columns, rows=list(period_result.rows))
            else:
                if period_result.columns and not merged_result.columns:
                    merged_result.columns = period_result.columns
                merged_result.rows.extend(period_result.rows)

        return merged_result

    def __aggregate_daily_to_monthly(self, daily_result: QueryResult) -> QueryResult:
        """Roll a Daily result up to one row per calendar month.

        Monthly reports are derived from the cached Daily data (summing PreTaxCost per
        month / resource-group / tag / currency, dated to the first of the month) so Monthly
        and Daily always reconcile and Monthly needs no separate Azure query (#2350).
        """
        columns = daily_result.columns
        if not daily_result.rows:
            return QueryResult(columns=columns, rows=[])

        column_names = [column.name for column in columns]
        df = pd.DataFrame.from_records(list(daily_result.rows), columns=column_names)
        # UsageDate is an integer YYYYMMDD; collapse it to the first of its month (YYYYMM01).
        df["UsageDate"] = (df["UsageDate"] // 100) * 100 + 1
        grouped = df.groupby(
            ["UsageDate", "ResourceGroup", "Tag", "Currency"], as_index=False).agg({"PreTaxCost": "sum"})
        ordered = grouped[["PreTaxCost", "UsageDate", "ResourceGroup", "Tag", "Currency"]]
        return QueryResult(columns=columns, rows=ordered.values.tolist())

    @staticmethod
    def __serialize_date(value: Optional[datetime]) -> Optional[str]:
        return value.date().isoformat() if value is not None else None

    @staticmethod
    def __is_period_final(period_to_date: Optional[datetime]) -> bool:
        """A period is final only once Azure has finished re-rating it.

        Month-to-date (no end date) is never final, and a period is only frozen once its last
        day is at least COST_DATA_SETTLING_DAYS in the past: the most recent days keep changing
        for a short settling window, and because refresh is idempotent a period frozen too early
        would keep serving still-incomplete data."""
        if period_to_date is None:
            return False
        today = datetime.now().date()
        return period_to_date.date() < today - timedelta(days=CostService.COST_DATA_SETTLING_DAYS)

    @staticmethod
    def __serialize_columns(columns) -> List[dict]:
        return [{"name": c.name, "type": c.type} for c in (columns or [])]

    async def __get_period_from_collection(self, costs_repo: CostsRepository, tag_name: str, tag_value: str,
                                           granularity: GranularityEnum, from_date: Optional[datetime],
                                           to_date: Optional[datetime], scope: str) -> Optional[QueryResult]:
        persisted = await costs_repo.get_cost_query_result(
            config.TRE_ID, scope, tag_name, tag_value, granularity,
            self.__serialize_date(from_date), self.__serialize_date(to_date))
        if persisted is None:
            return None
        # Only finalised periods are served from the collection; the still-settling current
        # month is always re-queried live.
        if not persisted.final:
            return None
        columns = [QueryColumn(name=c["name"], type=c["type"]) for c in persisted.columns]
        return QueryResult(columns=columns, rows=[list(r) for r in persisted.rows])

    async def __persist_period(self, costs_repo: CostsRepository, tag_name: str, tag_value: str,
                               granularity: GranularityEnum, from_date: Optional[datetime],
                               to_date: Optional[datetime], resource_groups: list, scope: str,
                               period_result: QueryResult, final: bool) -> None:
        await costs_repo.save_cost_query_result(
            tre_id=config.TRE_ID,
            scope=scope,
            tag_name=tag_name,
            tag_value=tag_value,
            granularity=granularity,
            from_date=self.__serialize_date(from_date),
            to_date=self.__serialize_date(to_date),
            resource_groups=list(resource_groups),
            columns=self.__serialize_columns(period_result.columns),
            rows=[list(r) for r in (period_result.rows or [])],
            final=final)

    async def refresh_costs(self, tre_id: str, granularity: GranularityEnum, from_date: Optional[datetime],
                            to_date: Optional[datetime], workspace_repo: WorkspaceRepository,
                            costs_repo: CostsRepository) -> dict:
        """Query Cost Management and persist each sub-period; returns collection stats.

        The only path that writes cost rows, invoked by the internal refresh endpoint. A period
        already finalised in the collection is reused instead of re-querying Azure, so the
        endpoint is idempotent and safe to call repeatedly (e.g. by the history backfill).
        Returns ``{"collected_periods": n, "total_rows": r}``; ``total_rows`` lets the backfill
        detect when it has walked back past the start of the data (a period with no rows).
        """
        subscription_ids = {config.SUBSCRIPTION_ID}
        subscription_ids.update(await self.__get_workspace_subscription_ids(workspace_repo))

        collected = 0
        total_rows = 0
        for subscription_id in subscription_ids:
            resource_groups = list(self.get_resource_groups_by_tag(self.TRE_ID_TAG, tre_id, subscription_id).keys())
            scope = "/subscriptions/{}".format(subscription_id)
            for period_from_date, period_to_date in self.split_query_period(from_date, to_date):
                # Idempotent: a period already finalised in the collection is reused rather than
                # re-queried, so repeated/backfill refreshes don't hit Cost Management again.
                period_result = await self.__get_period_from_collection(
                    costs_repo, self.TRE_ID_TAG, tre_id, granularity, period_from_date, period_to_date, scope)
                if period_result is None:
                    # Offload the blocking (synchronous) Cost Management SDK call to a worker
                    # thread so it doesn't starve the asyncio event loop (which would make the
                    # health probe fail and the platform return 500 for a long-running refresh).
                    period_result = await asyncio.to_thread(
                        self.query_costs_period,
                        self.TRE_ID_TAG, tre_id, granularity, period_from_date, period_to_date, resource_groups, scope)
                    await self.__persist_period(
                        costs_repo, self.TRE_ID_TAG, tre_id, granularity, period_from_date, period_to_date,
                        resource_groups, scope, period_result, final=self.__is_period_final(period_to_date))
                collected += 1
                total_rows += len(period_result.rows or [])
        return {"collected_periods": collected, "total_rows": total_rows}

    def query_costs_period(self, tag_name: str, tag_value: str,
                           granularity: GranularityEnum, from_date: Optional[datetime],
                           to_date: Optional[datetime],
                           resource_groups: list, scope: str) -> QueryResult:

        query_definition = self.build_query_definition(granularity, from_date, to_date, tag_name, tag_value, resource_groups)

        logger.debug(f"Querying cost management API with scope: {scope} and query definition: {query_definition}")

        try:
            result = self.client.query.usage(scope, query_definition)
        except ResourceNotFoundError as e:
            # when cost management API returns 404 with an message:
            # Given subscription {subscription_id} doesn't have valid WebDirect/AIRS offer type.
            # it means that the Azure subscription deosn't support cost management
            if "doesn't have valid WebDirect/AIRS" in e.message:
                logger.exception("Subscription doesn't support cost management")
                raise SubscriptionNotSupported(e)
            else:
                logger.exception("Unhandled Cost Management API error")
                raise e
        except HttpResponseError as e:
            logger.exception("Cost Management API error")
            if e.status_code == 429:
                # Too many requests - Request is throttled.
                # Retry after waiting for the time specified in the "x-ms-ratelimit-microsoft.consumption-retry-after" header.
                if self.RATE_LIMIT_RETRY_AFTER_HEADER_KEY in e.response.headers:
                    raise TooManyRequests(int(e.response.headers[self.RATE_LIMIT_RETRY_AFTER_HEADER_KEY]))
                else:
                    logger.warning(f"{self.RATE_LIMIT_RETRY_AFTER_HEADER_KEY} header was not found in response. Using default retry time of 60 seconds.")
                    raise TooManyRequests(60)  # Default retry after 60 seconds if header is not found
            elif e.status_code == 503:
                # Service unavailable - Service is temporarily unavailable.
                # Retry after waiting for the time specified in the "Retry-After" header.
                if self.SERVICE_UNAVAILABLE_RETRY_AFTER_HEADER_KEY in e.response.headers:
                    raise ServiceUnavailable(int(e.response.headers[self.SERVICE_UNAVAILABLE_RETRY_AFTER_HEADER_KEY]))
                else:
                    logger.exception(f"{self.SERVICE_UNAVAILABLE_RETRY_AFTER_HEADER_KEY} header was not found in response")
                    raise e
            else:
                raise e

        return result

    def build_query_definition(self, granularity: GranularityEnum, from_date: Optional[datetime],
                               to_date: Optional[datetime], tag_name: str, tag_value: str, resource_groups: list):
        tag_query_grouping: QueryGrouping = QueryGrouping(name=None, type="Tag")
        rg_query_grouping: QueryGrouping = QueryGrouping(name="ResourceGroup", type="Dimension")

        query_aggregation: QueryAggregation = QueryAggregation(name="PreTaxCost", function="Sum")
        query_aggregation_dict: Dict[str, QueryAggregation] = dict()
        query_aggregation_dict["totalCost"] = query_aggregation
        tag_query_filter: QueryFilter = QueryFilter(
            tags=QueryComparisonExpression(name=tag_name, operator="In", values=[tag_value]))
        rg_query_filter: QueryFilter = QueryFilter(
            dimensions=QueryComparisonExpression(name="ResourceGroup", operator="In", values=resource_groups)
        )
        query_filter: QueryFilter = QueryFilter(or_property=[tag_query_filter, rg_query_filter])
        query_grouping_list = list()
        query_grouping_list.append(rg_query_grouping)
        query_grouping_list.append(tag_query_grouping)
        query_dataset: QueryDataset = QueryDataset(
            granularity=granularity, aggregation=query_aggregation_dict,
            grouping=query_grouping_list, filter=query_filter)
        if from_date is None or to_date is None:
            query_definition: QueryDefinition = QueryDefinition(
                type=ExportType.actual_cost, timeframe=TimeframeType.MONTH_TO_DATE, dataset=query_dataset)
        else:
            query_time_period: QueryTimePeriod = QueryTimePeriod(
                from_property=from_date, to=to_date)
            query_definition: QueryDefinition = QueryDefinition(
                type=ExportType.actual_cost, timeframe=TimeframeType.CUSTOM,
                time_period=query_time_period, dataset=query_dataset)
        return query_definition

    def __query_result_to_dict(self, query_result: list, granularity: GranularityEnum):
        query_result_dict = dict()

        for row in query_result:
            # Daily and Monthly both include a leading date column, so the tag sits one column
            # further along than in an ungranular (None) result.
            tag = row[ResultColumn.Tag.value if granularity == GranularityEnum.none else ResultColumnDaily.Tag.value]

            if tag in query_result_dict.keys():
                query_result_dict[tag].append(row)
            else:
                query_result_dict[tag] = [row]

        return query_result_dict

    def __parse_cost_management_date_value(self, date_value: int):
        return datetime.strptime(str(date_value), "%Y%m%d").date()


@lru_cache(maxsize=None)
def cost_service_factory() -> CostService:
    return CostService()
