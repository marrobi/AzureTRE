from datetime import datetime, date, timedelta, UTC
import asyncio
import hashlib
from collections import OrderedDict
from enum import Enum
from functools import lru_cache
from typing import Dict, List, Optional, Tuple, Union

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
    CostRow, ExportedCostRow
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
    cache: "OrderedDict[str, CostCacheItem]"
    TRE_ID_TAG: str = "tre_id"
    TRE_CORE_SERVICE_ID_TAG: str = "tre_core_service_id"
    TRE_WORKSPACE_ID_TAG: str = "tre_workspace_id"
    TRE_SHARED_SERVICE_ID_TAG: str = "tre_shared_service_id"
    TRE_WORKSPACE_SERVICE_ID_TAG: str = "tre_workspace_service_id"
    TRE_USER_RESOURCE_ID_TAG: str = "tre_user_resource_id"
    TRE_UNTAGGED: str = ""
    RATE_LIMIT_RETRY_AFTER_HEADER_KEY: str = "x-ms-ratelimit-microsoft.costmanagement-entity-retry-after"
    SERVICE_UNAVAILABLE_RETRY_AFTER_HEADER_KEY: str = "Retry-After"
    CACHE_TTL: timedelta = timedelta(hours=2)
    # The cache is keyed per scope and day, so an unbounded dict would grow with every distinct
    # day ever reported on. Bound it and evict least-recently-used entries instead: this comfortably
    # holds a year of daily entries for the TRE-wide scope plus a few hundred workspaces.
    CACHE_MAX_ITEMS: int = 4096
    # Azure keeps re-rating the most recent days for a short window, so a period is only treated
    # as final (frozen in the collection and never re-queried) once its last day is at least this
    # many days in the past - otherwise idempotent refresh could freeze still-settling data.
    COST_DATA_SETTLING_DAYS: int = 4
    # How long a collected but still-settling day may be served from the collection before it is
    # re-queried. Keeping this at (a little over) the current-month refresh interval means reports
    # are served from the collection rather than repeatedly querying (and being throttled by)
    # Cost Management, without ever returning a figure older than one refresh cycle.
    SETTLING_DAY_MAX_AGE: timedelta = timedelta(hours=8)
    # Cap how many live Cost Management queries run concurrently: month-aligned splitting can
    # produce many sub-periods for a long cold range, and Cost Management throttles bursts.
    LIVE_QUERY_CONCURRENCY: int = 4

    def __init__(self) -> None:
        self.scope = "/subscriptions/{}".format(config.SUBSCRIPTION_ID)
        self.client = CostManagementClient(credential=credentials.get_credential())
        self.__resource_clients = {}
        self.get_resource_management_client(config.SUBSCRIPTION_ID)
        self.cache = OrderedDict()

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
        cached_item: Optional[CostCacheItem] = self.cache.get(key, None)

        # return None if key doesn't exist
        if cached_item is None:
            return None

        # return None if key expired
        if (datetime.now() > cached_item.ttl):
            # remove expired cache item
            self.cache.pop(key)
            return None

        # keep recently read days at the end so eviction drops the least recently used first
        self.cache.move_to_end(key)
        return cached_item.result

    def cache_result(self, key: str, result: QueryResult, timedelta: timedelta) -> None:
        """Add cost result to cache, evicting the least recently used entry when full.

        Args:
            key (str) : key of the cached item in cache.
            result (QueryResult) : cost query result to cache.
        """
        self.cache[key] = CostCacheItem(result, datetime.now() + timedelta)
        self.cache.move_to_end(key)
        while len(self.cache) > CostService.CACHE_MAX_ITEMS:
            self.cache.popitem(last=False)

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

        cost_report = CostReport(core_services=[], shared_services=[], workspaces=[], unattributed=[])

        cost_report.core_services = self.__extract_cost_rows_by_tag(
            granularity, query_result_dict, CostService.TRE_CORE_SERVICE_ID_TAG, tre_id)

        #  include deleted resources so their historical costs are still attributed
        shared_services = await shared_services_repo.get_shared_services()
        workspaces = await workspace_repo.get_workspaces()

        cost_report.shared_services = [
            self.__extract_cost_item(shared_service, granularity, query_result_dict, CostService.TRE_SHARED_SERVICE_ID_TAG)
            for shared_service in shared_services]

        cost_report.workspaces = [
            self.__extract_cost_item(workspace, granularity, query_result_dict, CostService.TRE_WORKSPACE_ID_TAG)
            for workspace in workspaces]

        cost_report.unattributed = self.__get_unattributed_costs(
            granularity, query_result_dict,
            {workspace.id for workspace in workspaces},
            {shared_service.id for shared_service in shared_services})

        return cost_report

    async def __get_workspace_subscription_ids(self, workspace_repo: WorkspaceRepository) -> list:
        #  we currently have to query ALL workspace resources to get the subscription ids to calculate costs for
        #  this may be able to change if we store subscriptions in config as per this issue: https://github.com/microsoft/AzureTRE/issues/4528
        #  deleted workspaces are included so cost they incurred in their own subscription is still reported
        workspaces = await workspace_repo.get_workspaces()
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
            #  the workspace (or its resource groups) may be deleted, or live in another
            #  subscription. Include deleted so a decommissioned workspace's historical costs are
            #  still reported, and read workspace_subscription_id defensively (it is only present
            #  for workspaces deployed to a separate subscription).
            try:
                workspace = await workspace_repo.get_workspace_by_id(workspace_id, include_deleted=True)
            except EntityDoesNotExist:
                raise WorkspaceDoesNotExist(f"workspace_id [{workspace_id}] does not exist")
            workspace_subscription_id = workspace.properties.get("workspace_subscription_id")
            if workspace_subscription_id:
                subscription_id = workspace_subscription_id
                resource_groups_dict = self.get_resource_groups_by_tag(self.TRE_WORKSPACE_ID_TAG, workspace_id, subscription_id)

        query_result = await self.query_costs(CostService.TRE_WORKSPACE_ID_TAG, workspace_id, granularity, from_date, to_date, list(resource_groups_dict.keys()), subscription_id, costs_repo)

        summarized_result = self.summarize_untagged(query_result, granularity, resource_groups_dict)
        query_result_dict = self.__query_result_to_dict(summarized_result, granularity)

        try:
            #  check if workspace is already loaded
            if 'workspace' not in locals() or workspace is None:
                workspace = await workspace_repo.get_workspace_by_id(workspace_id, include_deleted=True)
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

        column_index = {column.name: index for index, column in enumerate(query_result.columns)}
        cost_index = column_index["PreTaxCost"]
        tag_index = column_index["Tag"]
        resource_group_index = column_index["ResourceGroup"]
        # group by everything except the cost, which is summed
        key_indexes = [column_index[name] for name in
                       (["ResourceGroup", "Tag", "Currency"] if granularity == GranularityEnum.none
                        else ["UsageDate", "ResourceGroup", "Tag", "Currency"])]

        unattributable_resource_groups = set()
        aggregated: Dict[tuple, float] = {}
        for row in query_result.rows:
            tag = row[tag_index]
            if not tag:
                # fill the tag for untagged resources from the resource group's TRE tag
                resource_group = row[resource_group_index]
                tag = resource_groups_dict.get(resource_group)
                if tag is None:
                    # The resource group carries no TRE tag. This happens when an Azure service
                    # creates a secondary or managed resource group (e.g. Azure ML, Databricks)
                    # that inherits no TRE tags, or when the collection holds rows from a resource
                    # group that has since been removed or re-tagged. The rows stay unattributed
                    # and will not appear in any workspace or service breakdown.
                    unattributable_resource_groups.add(resource_group)
                    tag = ""
                row = list(row)
                row[tag_index] = tag
            key = tuple(row[index] for index in key_indexes)
            aggregated[key] = aggregated.get(key, 0.0) + row[cost_index]

        for resource_group in sorted(unattributable_resource_groups):
            logger.warning(
                f"Resource group '{resource_group}' has untagged costs but is not in the TRE "
                "resource groups list. These costs will not be attributed to a workspace or service."
            )

        # sorted so a report's rows are deterministic regardless of collection/query order
        return [[cost, *key] for key, cost in sorted(aggregated.items())]

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

    @staticmethod
    def __tag_id(tag_key: str, tag_name: str) -> Optional[str]:
        """Return the id from a ``"tag_name":"id"`` query-result key, or None if it is a different tag."""
        prefix = '"{}":"'.format(tag_name)
        if tag_key.startswith(prefix) and tag_key.endswith('"'):
            return tag_key[len(prefix):-1]
        return None

    def __get_unattributed_costs(self, granularity, query_result_dict, workspace_ids, shared_service_ids) -> List[CostRow]:
        """Cost tagged with a TRE workspace/shared-service id that has no database record.

        Captures resources that are gone from the database entirely (a hard-deleted workspace or a
        redeployed shared service) so their historical cost is surfaced as one 'unattributed' line
        instead of silently dropped. Only the two ids the core report attributes are considered, so
        a resource's cost is never both attributed and counted here."""
        rows = []
        for tag_key, tag_rows in query_result_dict.items():
            workspace_id = self.__tag_id(tag_key, self.TRE_WORKSPACE_ID_TAG)
            shared_service_id = self.__tag_id(tag_key, self.TRE_SHARED_SERVICE_ID_TAG)
            if (workspace_id is not None and workspace_id not in workspace_ids) \
                    or (shared_service_id is not None and shared_service_id not in shared_service_ids):
                rows.extend(tag_rows)
        return self.__rows_to_cost_rows(granularity, rows)

    def __rows_to_cost_rows(self, granularity, rows) -> List[CostRow]:
        """Aggregate raw query-result rows into a CostRow list, summing by date and currency."""
        aggregated: Dict[Tuple, float] = {}
        for row in rows:
            if granularity == GranularityEnum.none:
                cost = row[ResultColumn.Cost.value]
                currency = row[ResultColumn.Currency.value]
                cost_date = None
            else:
                cost = row[ResultColumnDaily.Cost.value]
                currency = row[ResultColumnDaily.Currency.value]
                cost_date = self.__parse_cost_management_date_value(row[ResultColumnDaily.Date.value])
            aggregated[(cost_date, currency)] = aggregated.get((cost_date, currency), 0.0) + cost
        return [self.__create_cost_row(cost, currency, cost_date)
                for (cost_date, currency), cost in aggregated.items()]

    async def __get_workspace_services_costs(self, granularity, query_result_dict,
                                             workspace_services_repo: WorkspaceServiceRepository,
                                             user_resource_repo: UserResourceRepository, workspace_id: str):
        workspace_services_costs = []
        workspace_services_list = await workspace_services_repo.get_workspace_services_for_workspace(workspace_id)
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
                                                              workspace_service.id,
                                                              include_deleted=True)]

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

    @staticmethod
    def __end_of_day(value: datetime) -> datetime:
        return value.replace(hour=23, minute=59, second=59, microsecond=0)

    async def query_costs(self, tag_name: str, tag_value: str,
                          granularity: GranularityEnum, from_date: Optional[datetime],
                          to_date: Optional[datetime],
                          resource_groups: list,
                          subscription_id: Optional[str] = None,
                          costs_repo: Optional[CostsRepository] = None) -> QueryResult:

        scope = "/subscriptions/{}".format(subscription_id) if subscription_id else self.scope

        # Cost data is only ever collected and stored at Daily granularity; Monthly and
        # ungranular reports are derived from those days. One collection therefore serves every
        # granularity, all three always reconcile, and no extra Azure round-trip is needed (#2350).
        daily_result = await self.__query_daily_costs(
            tag_name, tag_value, from_date, to_date, resource_groups, scope, costs_repo)

        if granularity == GranularityEnum.daily:
            return daily_result
        if granularity == GranularityEnum.monthly:
            return self.__aggregate_daily_to_monthly(daily_result)
        return self.__aggregate_daily_to_ungranular(daily_result)

    async def __query_daily_costs(self, tag_name: str, tag_value: str, from_date: Optional[datetime],
                                  to_date: Optional[datetime], resource_groups: list, scope: str,
                                  costs_repo: Optional[CostsRepository]) -> QueryResult:
        """Return the Daily rows for the report range, reusing collected days where possible.

        Finalised days come from the durable collection; any remaining days are queried live in
        month-aligned batches (Cost Management limits a query to one year) and each one is then
        persisted, so the next report reuses them.
        """
        first_day, last_day = self.__report_day_range(from_date, to_date)

        rows_by_day: Dict[date, List[list]] = {}
        total_days = (last_day - first_day).days + 1
        scope_key = self.__scope_cache_key(tag_name, tag_value, resource_groups, scope)

        # 1) in-memory cache, held per day so overlapping report ranges reuse the same days
        for day in self.__days_in_range(first_day, last_day):
            cached_rows = self.get_cached_result(f"{scope_key}_day{day.isoformat()}")
            if cached_rows is not None:
                rows_by_day[day] = cached_rows

        # 2) durable collection. A finalised day is immutable and always reused; a still-settling
        #    day is reused only while it is fresh, so the background refresh keeps current-month
        #    reports off Cost Management without ever serving a stale figure.
        if costs_repo is not None and len(rows_by_day) < total_days:
            collected = await costs_repo.get_cost_days(
                config.TRE_ID, scope, tag_name, tag_value, first_day.isoformat(), last_day.isoformat())
            for collected_day in collected:
                day = date.fromisoformat(collected_day.usage_date)
                if day in rows_by_day or not self.__is_collected_day_usable(collected_day):
                    continue
                rows_by_day[day] = [list(r) for r in collected_day.rows]

        # 3) anything still missing needs a live Cost Management query
        missing_days = [day for day in self.__days_in_range(first_day, last_day) if day not in rows_by_day]
        if missing_days:
            live_rows = await self.__query_live_daily_rows(
                tag_name, tag_value, missing_days, resource_groups, scope)
            for day in missing_days:
                rows_by_day[day] = live_rows.get(day, [])
            if costs_repo is not None:
                await self.__persist_days(
                    costs_repo, tag_name, tag_value, scope,
                    {day: rows_by_day[day] for day in missing_days})

        for day, day_rows in rows_by_day.items():
            self.cache_result(f"{scope_key}_day{day.isoformat()}", day_rows, CostService.CACHE_TTL)

        merged_rows = [row for day in sorted(rows_by_day) for row in rows_by_day[day]]
        return QueryResult(columns=self.__daily_columns(), rows=merged_rows)

    @staticmethod
    def __is_collected_day_usable(collected_day) -> bool:
        """A finalised day never changes; a still-settling one is only reused while fresh."""
        if collected_day.final:
            return True
        try:
            collected_at = datetime.fromisoformat(collected_day.collected_at)
        except ValueError:
            return False
        return datetime.now(UTC) - collected_at < CostService.SETTLING_DAY_MAX_AGE

    @staticmethod
    def __scope_cache_key(tag_name: str, tag_value: str, resource_groups: list, scope: str) -> str:
        """Cache key prefix for a scope; the resource-group list is hashed as it can be very long."""
        resource_group_digest = hashlib.sha256("_".join(sorted(resource_groups)).encode("utf-8")).hexdigest()[:16]
        return f"{tag_name}_{tag_value}_scope{scope}_rgs{resource_group_digest}"

    async def __query_live_daily_rows(self, tag_name: str, tag_value: str, days: List[date],
                                      resource_groups: list, scope: str) -> Dict[date, List[list]]:
        """Query Cost Management for the given days and bucket the returned rows by day.

        Runs off the event loop and concurrently: the SDK client is synchronous, so calling it
        inline would block the loop for the whole (often tens of seconds) query - long enough for
        the App Gateway health probe to fail and the backend to be marked unhealthy (see #2).
        Concurrency is bounded because Cost Management throttles bursts.
        """
        ranges = self.__contiguous_month_ranges(days)
        semaphore = asyncio.Semaphore(CostService.LIVE_QUERY_CONCURRENCY)

        async def __run_live_query(range_start: date, range_end: date) -> QueryResult:
            async with semaphore:
                return await asyncio.to_thread(
                    self.query_costs_period, tag_name, tag_value, GranularityEnum.daily,
                    datetime.combine(range_start, datetime.min.time()),
                    datetime.combine(range_end, datetime.min.time()),
                    resource_groups, scope)

        results = await asyncio.gather(*[__run_live_query(start, end) for start, end in ranges])

        rows_by_day: Dict[date, List[list]] = {}
        for result in results:
            for row in (result.rows or []):
                day = self.__parse_cost_management_date_value(row[ResultColumnDaily.Date.value])
                rows_by_day.setdefault(day, []).append(list(row))
        return rows_by_day

    @staticmethod
    def __report_day_range(from_date: Optional[datetime], to_date: Optional[datetime]) -> Tuple[date, date]:
        """Inclusive day range for a report; no dates means month to date."""
        if from_date is None or to_date is None:
            today = datetime.now(UTC).date()
            return today.replace(day=1), today
        return from_date.date(), to_date.date()

    @staticmethod
    def __days_in_range(first_day: date, last_day: date) -> List[date]:
        return [first_day + timedelta(days=offset) for offset in range((last_day - first_day).days + 1)]

    @staticmethod
    def __contiguous_month_ranges(days: List[date]) -> List[Tuple[date, date]]:
        """Group days into runs of consecutive days that never cross a calendar month boundary."""
        ranges: List[List[date]] = []
        for day in sorted(days):
            if ranges and day == ranges[-1][1] + timedelta(days=1) and (day.year, day.month) == (
                    ranges[-1][1].year, ranges[-1][1].month):
                ranges[-1][1] = day
            else:
                ranges.append([day, day])
        return [(start, end) for start, end in ranges]

    def __daily_columns(self) -> List[QueryColumn]:
        return [QueryColumn(name=name, type=column_type)
                for name, column_type in self.__export_result_columns(GranularityEnum.daily)]

    def __aggregate_daily_to_ungranular(self, daily_result: QueryResult) -> QueryResult:
        """Roll a Daily result up to a single row per resource group / tag / currency."""
        columns = [QueryColumn(name=name, type=column_type)
                   for name, column_type in self.__export_result_columns(GranularityEnum.none)]
        aggregated: Dict[tuple, float] = {}
        for row in (daily_result.rows or []):
            key = (row[ResultColumnDaily.ResourceGroup.value],
                   row[ResultColumnDaily.Tag.value],
                   row[ResultColumnDaily.Currency.value])
            aggregated[key] = aggregated.get(key, 0.0) + row[ResultColumnDaily.Cost.value]
        return QueryResult(columns=columns, rows=[[cost, *key] for key, cost in sorted(aggregated.items())])

    def __aggregate_daily_to_monthly(self, daily_result: QueryResult) -> QueryResult:
        """Roll a Daily result up to one row per calendar month.

        Monthly reports are derived from the cached Daily data (summing PreTaxCost per
        month / resource-group / tag / currency, dated to the first of the month) so Monthly
        and Daily always reconcile and Monthly needs no separate Azure query (#2350).
        """
        columns = daily_result.columns
        aggregated: Dict[tuple, float] = {}
        for row in (daily_result.rows or []):
            # UsageDate is an integer YYYYMMDD; collapse it to the first of its month (YYYYMM01).
            key = ((row[ResultColumnDaily.Date.value] // 100) * 100 + 1,
                   row[ResultColumnDaily.ResourceGroup.value],
                   row[ResultColumnDaily.Tag.value],
                   row[ResultColumnDaily.Currency.value])
            aggregated[key] = aggregated.get(key, 0.0) + row[ResultColumnDaily.Cost.value]
        return QueryResult(columns=columns, rows=[[cost, *key] for key, cost in sorted(aggregated.items())])

    @staticmethod
    def __is_day_final(usage_date: date) -> bool:
        """A day is final only once Azure has finished re-rating it.

        The most recent days keep changing for a short settling window, and because refresh is
        idempotent a day frozen too early would keep serving still-incomplete data. UTC is used
        consistently with the UTC collected_at timestamp so a day is not finalised early in a
        non-UTC deployment."""
        today = datetime.now(UTC).date()
        return usage_date < today - timedelta(days=CostService.COST_DATA_SETTLING_DAYS)

    async def __persist_days(self, costs_repo: CostsRepository, tag_name: str, tag_value: str,
                             scope: str, rows_by_day: Dict[date, List[list]]) -> None:
        """Write the days as transactional batches (one per month partition)."""
        days = [
            costs_repo.build_cost_day(
                tre_id=config.TRE_ID, scope=scope, tag_name=tag_name, tag_value=tag_value,
                usage_date=usage_date.isoformat(), rows=[list(r) for r in (rows or [])],
                final=self.__is_day_final(usage_date))
            for usage_date, rows in sorted(rows_by_day.items())]
        await costs_repo.save_cost_days(days)

    async def refresh_costs(self, tre_id: str, granularity: GranularityEnum, from_date: Optional[datetime],
                            to_date: Optional[datetime], workspace_repo: WorkspaceRepository,
                            costs_repo: CostsRepository) -> dict:
        """Query Cost Management and persist each sub-period; returns collection stats.

        The only path that writes cost rows, invoked by the internal refresh endpoint. Both the
        TRE-wide (``tre_id``) scope read by the core report and the per-workspace
        (``tre_workspace_id``) scope read by the workspace report are collected, so both report
        endpoints can be served from the durable collection instead of live Azure queries. A
        period already finalised in the collection is reused instead of re-querying Azure, so the
        endpoint is idempotent and safe to call repeatedly (e.g. by the history backfill).
        Returns ``{"collected_periods": n, "total_rows": r}``; ``total_rows`` lets the backfill
        detect when it has walked back past the start of the data (a period with no rows).
        """
        subscription_ids = {config.SUBSCRIPTION_ID}
        subscription_ids.update(await self.__get_workspace_subscription_ids(workspace_repo))

        collected = 0
        total_rows = 0

        # 1) TRE-wide scope (core report / whole-TRE breakdown).
        for subscription_id in subscription_ids:
            resource_groups = list(self.get_resource_groups_by_tag(self.TRE_ID_TAG, tre_id, subscription_id).keys())
            scope = "/subscriptions/{}".format(subscription_id)
            period_collected, period_rows = await self.__refresh_tag_periods(
                costs_repo, self.TRE_ID_TAG, tre_id, granularity, from_date, to_date, resource_groups, scope)
            collected += period_collected
            total_rows += period_rows

        # 2) Per-workspace scope (workspace report). The workspace report queries the
        #    tre_workspace_id tag, which is a different collection key, so unless it is collected
        #    here the workspace endpoint would always fall back to live Azure queries.
        for workspace in await workspace_repo.get_active_workspaces():
            resource_groups, scope = self.__resolve_workspace_resource_groups(workspace)
            if not resource_groups:
                continue
            period_collected, period_rows = await self.__refresh_tag_periods(
                costs_repo, self.TRE_WORKSPACE_ID_TAG, workspace.id, granularity,
                from_date, to_date, resource_groups, scope)
            collected += period_collected
            total_rows += period_rows

        return {"collected_periods": collected, "total_rows": total_rows}

    async def ingest_export_costs(self, tre_id: str, granularity: GranularityEnum, from_date: datetime,
                                  to_date: datetime, rows: List[ExportedCostRow],
                                  workspace_repo: WorkspaceRepository,
                                  costs_repo: CostsRepository,
                                  subscription_id: Optional[str] = None) -> dict:
        """Persist rows produced by a Cost Management export into the cost collection.

        Closed months are seeded/finalised from one-time Cost Management *exports* rather than
        Query API calls (see the "Seed a historical cost dataset with the Exports API" tutorial):
        an export returns the whole month in a single CSV, which avoids the Query API's
        one-year-per-request limit and its aggressive throttling of repeated historical queries.

        An export covers a single subscription, so the rows are only ever attributed to that
        subscription's scopes: the TRE-wide ``tre_id`` scope and the ``tre_workspace_id`` scope of
        each workspace that lives in it. Attributing them to every subscription the TRE spans
        would duplicate the exported subscription's costs once per subscription.

        The exported rows are bucketed into exactly the same period keys the read path looks up,
        applying the same "tag matches OR resource group belongs to this scope" filter the Query
        API applies, so a period ingested from an export is indistinguishable from one collected
        by ``refresh_costs``.

        The period is persisted as final: exports are only ever run for closed months.
        """
        subscription_id = subscription_id or config.SUBSCRIPTION_ID
        scope = "/subscriptions/{}".format(subscription_id)

        resource_groups = list(self.get_resource_groups_by_tag(self.TRE_ID_TAG, tre_id, subscription_id).keys())
        total_rows = await self.__ingest_tag_period(
            costs_repo, self.TRE_ID_TAG, tre_id, granularity, from_date, to_date,
            resource_groups, scope, rows)
        collected = 1

        row_index = self.__index_export_rows(rows)
        for workspace in await workspace_repo.get_active_workspaces():
            workspace_resource_groups, workspace_scope = self.__resolve_workspace_resource_groups(workspace)
            # only workspaces billed to the subscription this export covers
            if not workspace_resource_groups or workspace_scope != scope:
                continue
            persisted = await self.__ingest_tag_period(
                costs_repo, self.TRE_WORKSPACE_ID_TAG, workspace.id, granularity, from_date, to_date,
                workspace_resource_groups, workspace_scope,
                self.__export_rows_for_scope(row_index, rows, self.TRE_WORKSPACE_ID_TAG,
                                             workspace.id, workspace_resource_groups))
            collected += 1
            total_rows += persisted

        return {"collected_periods": collected, "total_rows": total_rows}

    async def get_subscription_ids(self, workspace_repo: WorkspaceRepository) -> List[str]:
        """Every subscription TRE costs can be incurred in, core first.

        The Cost Processor runs one export per subscription, so it asks the API which ones exist
        rather than duplicating the workspace lookup.
        """
        subscription_ids = [config.SUBSCRIPTION_ID]
        for subscription_id in await self.__get_workspace_subscription_ids(workspace_repo):
            if subscription_id not in subscription_ids:
                subscription_ids.append(subscription_id)
        return subscription_ids

    @staticmethod
    def __index_export_rows(rows: List[ExportedCostRow]) -> Tuple[Dict[str, List[int]], Dict[str, List[int]]]:
        """Index exported rows by tag and by resource group.

        An export can carry hundreds of thousands of rows, and every scope (the TRE plus one per
        workspace) filters that same list, so filtering per scope is O(rows x workspaces).
        Indexing once makes each workspace scope proportional to its own rows instead.
        """
        by_tag: Dict[str, List[int]] = {}
        by_resource_group: Dict[str, List[int]] = {}
        for position, row in enumerate(rows):
            by_tag.setdefault(row.tag, []).append(position)
            by_resource_group.setdefault(row.resource_group.lower(), []).append(position)
        return by_tag, by_resource_group

    @staticmethod
    def __export_rows_for_scope(index: Tuple[Dict[str, List[int]], Dict[str, List[int]]],
                                rows: List[ExportedCostRow], tag_name: str, tag_value: str,
                                resource_groups: list) -> List[ExportedCostRow]:
        """The rows a non-TRE-wide scope could possibly match, in their original order.

        A superset of what ``__export_rows_to_query_result`` keeps - it still applies the real
        filter - so this only narrows the work, it does not decide what is in scope.
        """
        by_tag, by_resource_group = index
        positions = set(by_tag.get(f'"{tag_name}":"{tag_value}"', ()))
        for resource_group in resource_groups:
            positions.update(by_resource_group.get(resource_group.lower(), ()))
        return [rows[position] for position in sorted(positions)]

    async def __ingest_tag_period(self, costs_repo: CostsRepository, tag_name: str, tag_value: str,
                                  granularity: GranularityEnum, from_date: datetime, to_date: datetime,
                                  resource_groups: list, scope: str,
                                  rows: List[ExportedCostRow]) -> int:
        """Persist the exported rows for this scope as one document per day of the period.

        Days the export returned no rows for are still written (as empty) so a month with idle
        days is not re-queried live forever.
        """
        query_result = self.__export_rows_to_query_result(
            GranularityEnum.daily, tag_name, tag_value, resource_groups, rows)

        rows_by_day: Dict[date, List[list]] = {}
        for row in query_result.rows:
            day = self.__parse_cost_management_date_value(row[ResultColumnDaily.Date.value])
            rows_by_day.setdefault(day, []).append(list(row))

        period_days = {day: rows_by_day.get(day, [])
                       for day in self.__days_in_range(from_date.date(), to_date.date())}
        await self.__persist_days(costs_repo, tag_name, tag_value, scope, period_days)
        return sum(len(day_rows) for day_rows in period_days.values())

    def __export_rows_to_query_result(self, granularity: GranularityEnum, tag_name: str, tag_value: str,
                                      resource_groups: list, rows: List[ExportedCostRow]) -> QueryResult:
        """Shape exported rows like a Cost Management query result for the given tag scope.

        Mirrors ``build_query_definition``'s filter (rows whose tag matches *or* whose resource
        group belongs to the scope) and column order, so the persisted rows can be consumed by
        ``summarize_untagged`` and the report builders unchanged.
        """
        wanted_tag = f'"{tag_name}":"{tag_value}"'
        resource_group_set = {rg.lower() for rg in resource_groups}
        # The TRE-wide (tre_id) period owns every TRE-tagged resource, so keep child-tag rows
        # (e.g. tre_workspace_id) even when the resource's group has since been deleted and is no
        # longer in the tre_id resource-group list; otherwise a deleted workspace's costs are lost.
        tre_wide = tag_name == self.TRE_ID_TAG
        columns = [QueryColumn(name=name, type=column_type) for name, column_type in
                   self.__export_result_columns(granularity)]

        aggregated: Dict[tuple, float] = {}
        for row in rows:
            in_scope = (row.tag == wanted_tag
                        or row.resource_group.lower() in resource_group_set
                        or (tre_wide and row.tag.startswith('"tre_')))
            if not in_scope:
                continue
            if granularity == GranularityEnum.none:
                key = (row.resource_group, row.tag, row.currency)
            else:
                key = (row.date, row.resource_group, row.tag, row.currency)
            aggregated[key] = aggregated.get(key, 0.0) + row.cost

        result_rows = [[cost, *key] for key, cost in sorted(aggregated.items())]
        return QueryResult(columns=columns, rows=result_rows)

    @staticmethod
    def __export_result_columns(granularity: GranularityEnum) -> List[Tuple[str, str]]:
        if granularity == GranularityEnum.none:
            return [("PreTaxCost", "Number"), ("ResourceGroup", "String"),
                    ("Tag", "String"), ("Currency", "String")]
        return [("PreTaxCost", "Number"), ("UsageDate", "Number"), ("ResourceGroup", "String"),
                ("Tag", "String"), ("Currency", "String")]

    def __resolve_workspace_resource_groups(self, workspace: Resource) -> Tuple[list, str]:
        """Resolve a workspace's resource groups and Cost Management scope.

        Mirrors ``query_tre_workspace_costs``: resource groups tagged with the workspace id are
        looked up in the core subscription first and, only if none are found, in the workspace's
        own subscription. The returned scope matches the one the read path uses so the persisted
        period keys line up with what the workspace report looks up.
        """
        resource_groups_dict = self.get_resource_groups_by_tag(self.TRE_WORKSPACE_ID_TAG, workspace.id)
        subscription_id = None
        if not resource_groups_dict:
            workspace_subscription_id = workspace.properties.get("workspace_subscription_id")
            if workspace_subscription_id:
                subscription_id = workspace_subscription_id
                resource_groups_dict = self.get_resource_groups_by_tag(
                    self.TRE_WORKSPACE_ID_TAG, workspace.id, subscription_id)
        scope = "/subscriptions/{}".format(subscription_id) if subscription_id else self.scope
        return list(resource_groups_dict.keys()), scope

    async def __refresh_tag_periods(self, costs_repo: CostsRepository, tag_name: str, tag_value: str,
                                    granularity: GranularityEnum, from_date: Optional[datetime],
                                    to_date: Optional[datetime], resource_groups: list, scope: str) -> Tuple[int, int]:
        """Collect and persist the requested range one day at a time.

        Idempotent: days already finalised in the collection are reused rather than re-queried,
        so repeated/backfill refreshes don't hit Cost Management again. Still-settling days are
        always re-collected - keeping them fresh is the point of the current-month refresh.
        """
        first_day, last_day = self.__report_day_range(from_date, to_date)
        collected_rows: Dict[date, List[list]] = {}
        collected = await costs_repo.get_cost_days(
            config.TRE_ID, scope, tag_name, tag_value, first_day.isoformat(), last_day.isoformat())
        for collected_day in collected:
            if collected_day.final:
                collected_rows[date.fromisoformat(collected_day.usage_date)] = [list(r) for r in collected_day.rows]

        missing_days = [day for day in self.__days_in_range(first_day, last_day) if day not in collected_rows]
        if missing_days:
            live_rows = await self.__query_live_daily_rows(
                tag_name, tag_value, missing_days, resource_groups, scope)
            for day in missing_days:
                collected_rows[day] = live_rows.get(day, [])
            await self.__persist_days(
                costs_repo, tag_name, tag_value, scope,
                {day: collected_rows[day] for day in missing_days})

        total_rows = sum(len(rows) for rows in collected_rows.values())
        return len(collected_rows), total_rows

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
        if resource_groups:
            rg_query_filter: QueryFilter = QueryFilter(
                dimensions=QueryComparisonExpression(name="ResourceGroup", operator="In", values=resource_groups)
            )
            query_filter: QueryFilter = QueryFilter(or_property=[tag_query_filter, rg_query_filter])
        else:
            # A deleted resource has no current resource groups; filter on the tag alone so its
            # historical costs are still returned (Cost Management rejects an empty ResourceGroup "In").
            query_filter = tag_query_filter
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
                from_property=from_date,
                # Cost Management applies the custom period at day granularity and Microsoft's own
                # examples set `to` to end-of-day; pin it to 23:59:59 so the last day of the range
                # (e.g. the final day of a month-aligned split, or the last day of a month) is
                # always included rather than silently dropped.
                to=self.__end_of_day(to_date))
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
