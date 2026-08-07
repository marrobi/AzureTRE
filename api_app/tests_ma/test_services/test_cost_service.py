from unittest.mock import AsyncMock
from mock import patch
import pytest
from db.repositories.costs import CostsRepository
from models.domain.costs import ExportedCostRow, GranularityEnum, PersistedCostDay
from models.domain.shared_service import SharedService, ResourceType
from models.domain.user_resource import UserResource
from models.domain.workspace import Workspace
from models.domain.workspace_service import WorkspaceService
from services.cost_service import CostService, SubscriptionNotSupported
from datetime import date, datetime, timedelta, timezone
from azure.mgmt.costmanagement.models import QueryResult, TimeframeType, QueryDefinition, QueryColumn
from azure.core.exceptions import ResourceNotFoundError

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def clear_lru_cache():
    CostService.cache_clear()
    yield
    CostService.cache_clear()


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_with_granularity_none_returns_correct_cost_report(get_resource_groups_by_tag_mock, client_mock,
                                                                                 shared_service_repo_mock, workspace_repo_mock):
    client_mock.return_value.query.usage.return_value = __get_cost_management_query_result()
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    cost_service = CostService()
    cost_report = await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, datetime.now(), datetime.now(), workspace_repo_mock, shared_service_repo_mock)

    assert len(cost_report.core_services) == 1
    assert cost_report.core_services[0].cost == 37.6
    assert cost_report.core_services[0].date is None
    assert len(cost_report.shared_services) == 2
    assert cost_report.shared_services[0].id == "848e8eb5-0df6-4d0f-9162-afd9a3fa0631"
    assert cost_report.shared_services[0].name == "Shared service tre-shared-service-firewall"
    assert len(cost_report.shared_services[0].costs) == 1
    assert cost_report.shared_services[0].costs[0].cost == 6.8
    assert cost_report.shared_services[1].id == "f16d0324-9027-4448-b69b-2d48d925e6c0"
    assert cost_report.shared_services[1].name == "Shared service tre-shared-service-gitea"
    assert len(cost_report.shared_services[1].costs) == 1
    assert cost_report.shared_services[1].costs[0].cost == 4.8
    assert len(cost_report.workspaces) == 2
    assert cost_report.workspaces[0].id == "19b7ce24-aa35-438c-adf6-37e6762911a6"
    assert cost_report.workspaces[0].name == "the workspace display name1"
    assert len(cost_report.workspaces[0].costs) == 1
    assert cost_report.workspaces[0].costs[0].cost == 1.8
    assert cost_report.workspaces[1].id == "d680d6b7-d1d9-411c-9101-0793da980c81"
    assert cost_report.workspaces[1].name == "the workspace display name2"
    assert len(cost_report.workspaces[1].costs) == 2
    assert cost_report.workspaces[1].costs[0].cost == 5.8
    assert cost_report.workspaces[1].costs[0].currency == "ILS"
    assert cost_report.workspaces[1].costs[1].cost == 2.8
    assert cost_report.workspaces[1].costs[1].currency == "USD"


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_with_granularity_daily_returns_correct_cost_report(
        get_resource_groups_by_tag_mock, client_mock, shared_service_repo_mock, workspace_repo_mock):
    client_mock.return_value.query.usage.return_value = __set_cost_management_client_mock_query_result()
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    cost_service = CostService()
    cost_report = await cost_service.query_tre_costs(
        "guy22", GranularityEnum.daily, datetime(2022, 5, 1), datetime(2022, 5, 3),
        workspace_repo_mock, shared_service_repo_mock)

    assert len(cost_report.core_services) == 3
    assert cost_report.core_services[0].cost == 31.6
    assert cost_report.core_services[0].date == date(2022, 5, 1)
    assert len(cost_report.shared_services) == 2
    assert cost_report.shared_services[0].id == "848e8eb5-0df6-4d0f-9162-afd9a3fa0631"
    assert cost_report.shared_services[0].name == "Shared service tre-shared-service-firewall"
    assert len(cost_report.shared_services[0].costs) == 3
    assert cost_report.shared_services[0].costs[0].cost == 3.8
    assert cost_report.shared_services[0].costs[0].date == date(2022, 5, 1)
    assert cost_report.shared_services[0].costs[1].cost == 4.8
    assert cost_report.shared_services[0].costs[1].date == date(2022, 5, 2)
    assert cost_report.shared_services[0].costs[2].cost == 5.8
    assert cost_report.shared_services[0].costs[2].date == date(2022, 5, 3)
    assert cost_report.shared_services[1].id == "f16d0324-9027-4448-b69b-2d48d925e6c0"
    assert cost_report.shared_services[1].name == "Shared service tre-shared-service-gitea"
    assert len(cost_report.shared_services[1].costs) == 3
    assert cost_report.shared_services[1].costs[0].cost == 2.8
    assert cost_report.shared_services[1].costs[0].date == date(2022, 5, 1)
    assert cost_report.shared_services[1].costs[1].cost == 3.8
    assert cost_report.shared_services[1].costs[1].date == date(2022, 5, 2)
    assert cost_report.shared_services[1].costs[2].cost == 4.8
    assert cost_report.shared_services[1].costs[2].date == date(2022, 5, 3)
    assert len(cost_report.workspaces) == 2
    assert cost_report.workspaces[0].id == "19b7ce24-aa35-438c-adf6-37e6762911a6"
    assert cost_report.workspaces[0].name == "the workspace display name1"
    assert len(cost_report.workspaces[0].costs) == 3
    assert cost_report.workspaces[0].costs[0].cost == 1.8
    assert cost_report.workspaces[0].costs[0].date == date(2022, 5, 1)
    assert cost_report.workspaces[0].costs[1].cost == 2.8
    assert cost_report.workspaces[0].costs[1].date == date(2022, 5, 2)
    assert cost_report.workspaces[0].costs[2].cost == 3.8
    assert cost_report.workspaces[0].costs[2].date == date(2022, 5, 3)
    assert cost_report.workspaces[1].id == "d680d6b7-d1d9-411c-9101-0793da980c81"
    assert cost_report.workspaces[1].name == "the workspace display name2"
    assert len(cost_report.workspaces[1].costs) == 4
    assert cost_report.workspaces[1].costs[0].cost == 4.8
    assert cost_report.workspaces[1].costs[0].date == date(2022, 5, 1)
    assert cost_report.workspaces[1].costs[1].cost == 5.8
    assert cost_report.workspaces[1].costs[1].date == date(2022, 5, 2)
    assert cost_report.workspaces[1].costs[2].cost == 16.8
    assert cost_report.workspaces[1].costs[2].date == date(2022, 5, 3)
    assert cost_report.workspaces[1].costs[2].currency == "ILS"
    assert cost_report.workspaces[1].costs[3].cost == 6.8
    assert cost_report.workspaces[1].costs[3].date == date(2022, 5, 3)
    assert cost_report.workspaces[1].costs[3].currency == "USD"


def __get_monthly_source_daily_query_result():
    # Monthly reports are derived from Daily data, so Cost Management is queried at Daily
    # granularity and the service rolls the days up per month.
    query_result = QueryResult()
    query_result.columns = [
        QueryColumn(name="PreTaxCost", type="Number"),
        QueryColumn(name="UsageDate", type="Number"),
        QueryColumn(name="ResourceGroup", type="String"),
        QueryColumn(name="Tag", type="String"),
        QueryColumn(name="Currency", type="String")]
    query_result.rows = [
        # core: May = 10 + 20 = 30, June = 40
        [10.0, 20220501, 'rg-guy22', '"tre_core_service_id":"guy22"', 'USD'],
        [20.0, 20220502, 'rg-guy22', '"tre_core_service_id":"guy22"', 'USD'],
        [40.0, 20220601, 'rg-guy22', '"tre_core_service_id":"guy22"', 'USD'],
        # shared service firewall: May = 6.8
        [6.8, 20220501, 'rg-guy22', '"tre_shared_service_id":"848e8eb5-0df6-4d0f-9162-afd9a3fa0631"', 'USD'],
        # workspace: May = 1.0 + 0.8 = 1.8
        [1.0, 20220501, 'rg-guy22-ws-11a6', '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"', 'USD'],
        [0.8, 20220502, 'rg-guy22-ws-11a6', '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"', 'USD'],
    ]
    return query_result


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_with_granularity_monthly_aggregates_daily(
        get_resource_groups_by_tag_mock, client_mock, shared_service_repo_mock, workspace_repo_mock):
    client_mock.return_value.query.usage.side_effect = __daily_result_within_queried_range(
        __get_monthly_source_daily_query_result())
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    cost_service = CostService()
    cost_report = await cost_service.query_tre_costs(
        "guy22", GranularityEnum.monthly, datetime(2022, 5, 1), datetime(2022, 6, 1),
        workspace_repo_mock, shared_service_repo_mock)

    # Monthly is queried at Daily granularity from Cost Management, then aggregated per month.
    # Missing days are queried in month-aligned batches, so a May-June range takes two queries.
    assert client_mock.return_value.query.usage.call_count == 2
    query_definition = client_mock.return_value.query.usage.call_args[0][1]
    assert query_definition.dataset.granularity == GranularityEnum.daily

    # Daily rows are rolled up to one row per calendar month, dated to the first of the month.
    assert len(cost_report.core_services) == 2
    assert cost_report.core_services[0].cost == 30.0
    assert cost_report.core_services[0].date == date(2022, 5, 1)
    assert cost_report.core_services[1].cost == 40.0
    assert cost_report.core_services[1].date == date(2022, 6, 1)
    firewall = next(s for s in cost_report.shared_services if s.id == "848e8eb5-0df6-4d0f-9162-afd9a3fa0631")
    assert firewall.costs[0].cost == 6.8
    assert firewall.costs[0].date == date(2022, 5, 1)
    workspace = next(w for w in cost_report.workspaces if w.id == "19b7ce24-aa35-438c-adf6-37e6762911a6")
    assert workspace.costs[0].cost == 1.8
    assert workspace.costs[0].date == date(2022, 5, 1)


def __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock):
    get_resource_groups_by_tag_mock.return_value = {
        'rg-guy22': '"tre_id":"guy22"',
        'rg-guy22-ws-11a6': '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"',
        'rg-guy22-ws-0c81': '"tre_workspace_id":"d680d6b7-d1d9-411c-9101-0793da980c81"'
    }


async def test_summarize_untagged_uses_rg_tag_as_fallback_for_untagged_resources():
    # Resources in a known TRE resource group that carry no individual tag should be
    # attributed to the resource group's TRE tag (the existing "untagged fallback").
    query_result = QueryResult()
    query_result.columns = [
        QueryColumn(name="PreTaxCost", type="Number"),
        QueryColumn(name="ResourceGroup", type="String"),
        QueryColumn(name="Tag", type="String"),
        QueryColumn(name="Currency", type="String")]
    query_result.rows = [
        [10.0, 'rg-guy22-ws-11a6', '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"', 'USD'],
        # untagged resource in a known RG — should be attributed to the workspace
        [5.0, 'rg-guy22-ws-11a6', '', 'USD'],
    ]
    resource_groups_dict = {'rg-guy22-ws-11a6': '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"'}

    cost_service = CostService()
    rows = cost_service.summarize_untagged(query_result, GranularityEnum.none, resource_groups_dict)

    # both rows should be merged under the workspace tag
    assert len(rows) == 1
    assert rows[0][0] == 15.0
    assert rows[0][2] == '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"'


async def test_summarize_untagged_logs_warning_and_does_not_raise_for_unknown_rg(caplog):
    # When a cost result row references a resource group that is NOT in resource_groups_dict
    # (e.g. a managed/secondary RG created by an Azure service, or stale data from the
    # Cosmos collection after a workspace was deleted), summarize_untagged must not raise a
    # KeyError.  Instead it logs a warning and leaves those rows unattributed.
    import logging
    query_result = QueryResult()
    query_result.columns = [
        QueryColumn(name="PreTaxCost", type="Number"),
        QueryColumn(name="ResourceGroup", type="String"),
        QueryColumn(name="Tag", type="String"),
        QueryColumn(name="Currency", type="String")]
    query_result.rows = [
        # row from a known RG — should be attributed normally
        [10.0, 'rg-guy22-ws-11a6', '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"', 'USD'],
        # row from an unrecognised secondary RG with no TRE tag
        [7.5, 'databricks-rg-ws-external', '', 'USD'],
    ]
    # only the known RG is present in the dict
    resource_groups_dict = {'rg-guy22-ws-11a6': '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"'}

    cost_service = CostService()
    with caplog.at_level(logging.WARNING):
        rows = cost_service.summarize_untagged(query_result, GranularityEnum.none, resource_groups_dict)

    # no KeyError: the call returns normally
    # the known resource is still present
    assert any(
        row[2] == '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"' for row in rows
    )
    # a warning was logged for the unknown resource group
    assert any('databricks-rg-ws-external' in record.message for record in caplog.records)


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_with_granularity_none_and_missing_costs_data_returns_empty_cost_report(get_resource_groups_by_tag_mock,
                                                                                                      client_mock,
                                                                                                      shared_service_repo_mock,
                                                                                                      workspace_repo_mock):
    query_result = QueryResult()
    query_result.rows = [
    ]
    query_result.columns = [QueryColumn(name="PreTaxCost", type="Number"),
                            QueryColumn(name="ResourceGroup", type="String"),
                            QueryColumn(name="Tag", type="String"),
                            QueryColumn(name="Currency", type="String")]

    client_mock.return_value.query.usage.return_value = query_result

    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    cost_service = CostService()
    cost_report = await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, datetime.now(), datetime.now(), workspace_repo_mock, shared_service_repo_mock)

    assert len(cost_report.core_services) == 0
    assert len(cost_report.shared_services) == 2
    assert len(cost_report.shared_services[0].costs) == 0
    assert len(cost_report.shared_services[1].costs) == 0
    assert len(cost_report.workspaces) == 2
    assert len(cost_report.workspaces[0].costs) == 0
    assert len(cost_report.workspaces[1].costs) == 0


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_for_unsupported_subscription_raises_subscription_not_supported_exception(get_resource_groups_by_tag_mock,
                                                                                                        client_mock,
                                                                                                        shared_service_repo_mock,
                                                                                                        workspace_repo_mock):

    client_mock.return_value.query.usage.side_effect = ResourceNotFoundError({
        "error": {
            "code": "NotFound",
            "message": "Given subscription xxx doesn't have valid WebDirect/AIRS offer type. (Request ID: 12daa3b6-8a53-4759-97ba-511ece1ac95b)"
        }
    })

    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    cost_service = CostService()

    with pytest.raises(SubscriptionNotSupported):
        await cost_service.query_tre_costs(
            "guy22", GranularityEnum.none, datetime.now(), datetime.now(), workspace_repo_mock, shared_service_repo_mock)


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_with_granularity_daily_and_missing_costs_data_returns_empty_cost_report(get_resource_groups_by_tag_mock,
                                                                                                       client_mock,
                                                                                                       shared_service_repo_mock,
                                                                                                       workspace_repo_mock):
    query_result = QueryResult()
    query_result.rows = [
    ]

    query_result.columns = [QueryColumn(name="PreTaxCost", type="Number"),
                            QueryColumn(name="UsageDate", type="DateTime"),
                            QueryColumn(name="ResourceGroup", type="String"),
                            QueryColumn(name="Tag", type="String"),
                            QueryColumn(name="Currency", type="String")]

    client_mock.return_value.query.usage.return_value = query_result

    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    cost_service = CostService()
    cost_report = await cost_service.query_tre_costs(
        "guy22", GranularityEnum.daily, datetime.now(), datetime.now(), workspace_repo_mock, shared_service_repo_mock)

    assert len(cost_report.core_services) == 0
    assert len(cost_report.shared_services) == 2
    assert len(cost_report.shared_services[0].costs) == 0
    assert len(cost_report.shared_services[1].costs) == 0
    assert len(cost_report.workspaces) == 2
    assert len(cost_report.workspaces[0].costs) == 0
    assert len(cost_report.workspaces[1].costs) == 0


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_with_granularity_none_and_display_name_data_returns_template_name_in_cost_report(get_resource_groups_by_tag_mock,
                                                                                                                client_mock,
                                                                                                                shared_service_repo_mock,
                                                                                                                workspace_repo_mock):
    client_mock.return_value.query.usage.return_value = __get_cost_management_query_result()
    __set_shared_service_repo_mock_return_value_without_display_name(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value_without_display_name(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    cost_service = CostService()
    cost_report = await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, datetime.now(), datetime.now(), workspace_repo_mock, shared_service_repo_mock)

    assert len(cost_report.core_services) == 1
    assert cost_report.core_services[0].cost == 37.6
    assert cost_report.core_services[0].date is None
    assert len(cost_report.shared_services) == 2
    assert cost_report.shared_services[0].id == "848e8eb5-0df6-4d0f-9162-afd9a3fa0631"
    assert cost_report.shared_services[0].name == "tre-shared-service-firewall"
    assert len(cost_report.shared_services[0].costs) == 1
    assert cost_report.shared_services[0].costs[0].cost == 6.8
    assert cost_report.shared_services[1].id == "f16d0324-9027-4448-b69b-2d48d925e6c0"
    assert cost_report.shared_services[1].name == "tre-shared-service-gitea"
    assert len(cost_report.shared_services[1].costs) == 1
    assert cost_report.shared_services[1].costs[0].cost == 4.8
    assert len(cost_report.workspaces) == 2
    assert cost_report.workspaces[0].id == "19b7ce24-aa35-438c-adf6-37e6762911a6"
    assert cost_report.workspaces[0].name == "tre-workspace-base"
    assert len(cost_report.workspaces[0].costs) == 1
    assert cost_report.workspaces[0].costs[0].cost == 1.8
    assert cost_report.workspaces[1].id == "d680d6b7-d1d9-411c-9101-0793da980c81"
    assert cost_report.workspaces[1].name == "tre-workspace-base"
    assert cost_report.workspaces[1].costs[0].cost == 5.8
    assert cost_report.workspaces[1].costs[0].currency == "ILS"
    assert cost_report.workspaces[1].costs[1].cost == 2.8
    assert cost_report.workspaces[1].costs[1].currency == "USD"


@pytest.mark.parametrize("from_date,to_date", [(None, datetime.now()), (datetime.now(), None), (None, None)])
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_with_dates_set_as_none_calls_client_with_month_to_date(get_resource_groups_by_tag_mock,
                                                                                      client_mock, shared_service_repo_mock,
                                                                                      workspace_repo_mock, from_date,
                                                                                      to_date):
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    cost_service = CostService()
    CostService.cache_clear()
    await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, from_date, to_date, workspace_repo_mock, shared_service_repo_mock)

    query_definition: QueryDefinition = client_mock.return_value.query.usage.call_args_list[0][0][1]
    # Month to date is resolved to an explicit first-of-month..today range so the days it covers
    # can be served from (and written to) the durable per-day collection.
    assert query_definition.timeframe == TimeframeType.CUSTOM
    today = datetime.now(timezone.utc).date()
    assert query_definition.time_period.from_property.date() == today.replace(day=1)


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_with_dates_set_as_none_calls_client_with_custom_dates(get_resource_groups_by_tag_mock,
                                                                                     client_mock, shared_service_repo_mock,
                                                                                     workspace_repo_mock):
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    from_date = datetime.now() - timedelta(days=10)
    to_date = datetime.now()

    cost_service = CostService()
    await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, from_date, to_date, workspace_repo_mock, shared_service_repo_mock)

    query_definition: QueryDefinition = client_mock.return_value.query.usage.call_args_list[0][0][1]
    assert query_definition.timeframe == TimeframeType.CUSTOM
    assert query_definition.time_period.from_property.date() == from_date.date()
    # the range is split per calendar month, so the end of the range is on the last query
    last_query_definition: QueryDefinition = client_mock.return_value.query.usage.call_args_list[-1][0][1]
    # `to` is pinned to end-of-day so Cost Management includes the whole final day of the range
    # rather than dropping it (see cost_service.build_query_definition).
    assert last_query_definition.time_period.to.date() == to_date.date()


@pytest.mark.asyncio
@patch('services.cost_service.CostManagementClient')
async def test_build_query_definition_makes_to_date_inclusive_end_of_day(client_mock):
    # A custom period's `to` must be pinned to end-of-day so Cost Management includes the whole
    # last day (e.g. the last day of a month-aligned split) rather than dropping it.
    cost_service = CostService()
    from_date = datetime(2022, 6, 1)
    to_date = datetime(2022, 6, 30)

    query_definition = cost_service.build_query_definition(
        GranularityEnum.daily, from_date, to_date, CostService.TRE_ID_TAG, "guy22", ["rg-guy22"])

    assert query_definition.timeframe == TimeframeType.CUSTOM
    assert query_definition.time_period.from_property == from_date
    assert query_definition.time_period.to == datetime(2022, 6, 30, 23, 59, 59)


@pytest.mark.asyncio
@patch('services.cost_service.CostManagementClient')
async def test_build_query_definition_filters_on_tag_only_when_no_resource_groups(client_mock):
    # A deleted resource has no current resource groups; the query must filter on the tag alone -
    # Cost Management rejects an empty ResourceGroup "In" filter (BadRequest).
    cost_service = CostService()

    query_definition = cost_service.build_query_definition(
        GranularityEnum.daily, datetime(2022, 6, 1), datetime(2022, 6, 30),
        CostService.TRE_WORKSPACE_ID_TAG, "deleted-ws", [])

    query_filter = query_definition.dataset.filter
    assert query_filter.or_property is None
    assert query_filter.tags.name == CostService.TRE_WORKSPACE_ID_TAG
    assert query_filter.tags.values == ["deleted-ws"]


@pytest.mark.asyncio
@patch('services.cost_service.CostManagementClient')
async def test_contiguous_month_ranges_batches_days_into_calendar_months(client_mock):
    cost_service = CostService()
    days = [date(2022, 1, 30) + timedelta(days=offset) for offset in range(5)]

    ranges = cost_service._CostService__contiguous_month_ranges(days)

    # a batch never crosses a calendar month boundary, so each live query stays month-aligned
    # (and well within Cost Management's one-year-per-query limit)
    assert ranges == [
        (date(2022, 1, 30), date(2022, 1, 31)),
        (date(2022, 2, 1), date(2022, 2, 3)),
    ]


@pytest.mark.asyncio
@patch('services.cost_service.CostManagementClient')
async def test_contiguous_month_ranges_splits_on_gaps(client_mock):
    cost_service = CostService()
    # days already collected leave gaps; only the missing runs are queried
    days = [date(2022, 3, 1), date(2022, 3, 2), date(2022, 3, 10)]

    ranges = cost_service._CostService__contiguous_month_ranges(days)

    assert ranges == [
        (date(2022, 3, 1), date(2022, 3, 2)),
        (date(2022, 3, 10), date(2022, 3, 10)),
    ]


@pytest.mark.asyncio
@patch('services.cost_service.CostManagementClient')
async def test_contiguous_month_ranges_covers_multi_year_range_without_overlap(client_mock):
    cost_service = CostService()
    first_day, last_day = date(2022, 1, 1), date(2025, 1, 1)
    days = [first_day + timedelta(days=offset) for offset in range((last_day - first_day).days + 1)]

    ranges = cost_service._CostService__contiguous_month_ranges(days)

    # a multi year range is split into more than one query and fully covered without overlap
    assert len(ranges) > 1
    assert ranges[0][0] == first_day
    assert ranges[-1][1] == last_day
    for range_start, range_end in ranges:
        assert (range_start.year, range_start.month) == (range_end.year, range_end.month)
    for previous, current in zip(ranges, ranges[1:]):
        assert current[0] == previous[1] + timedelta(days=1)


@pytest.mark.asyncio
@patch('services.cost_service.CostManagementClient')
async def test_report_day_range_defaults_to_month_to_date(client_mock):
    cost_service = CostService()
    today = datetime.now(timezone.utc).date()

    # no dates means month to date, resolved to explicit days so the collection can serve them
    assert cost_service._CostService__report_day_range(None, None) == (today.replace(day=1), today)
    assert cost_service._CostService__report_day_range(datetime(2022, 1, 15), datetime(2022, 3, 10)) == (
        date(2022, 1, 15), date(2022, 3, 10))


@pytest.mark.asyncio
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.query_costs_period')
async def test_query_costs_daily_over_multiple_years_has_correct_totals_and_no_seam_gaps(
        query_costs_period_mock, client_mock):
    # Simulate several years of *daily* costs with a known, fixed cost per day so the merged
    # multi-year report can be verified exactly: no day may be dropped or double-counted at
    # the 364-day split seams, and the total must equal cost-per-day x number-of-days (#2350).
    cost_service = CostService()

    from_date = datetime(2021, 1, 1)
    to_date = datetime(2025, 12, 31)
    daily_cost = 1.23
    tag_name = CostService.TRE_ID_TAG
    tag_value = "guy22"

    def __synthesize_daily_period(t_name, t_value, granularity, period_from, period_to, resource_groups, scope):
        query_result = QueryResult()
        query_result.columns = [
            QueryColumn(name="PreTaxCost", type="Number"),
            QueryColumn(name="UsageDate", type="Number"),
            QueryColumn(name="ResourceGroup", type="String"),
            QueryColumn(name="Tag", type="String"),
            QueryColumn(name="Currency", type="String")]
        rows = []
        day = period_from
        while day <= period_to:
            rows.append([daily_cost, int(day.strftime("%Y%m%d")), "rg-guy22",
                         '"{}":"{}"'.format(t_name, t_value), "USD"])
            day += timedelta(days=1)
        query_result.rows = rows
        return query_result

    query_costs_period_mock.side_effect = __synthesize_daily_period

    expected_periods = __month_ranges(from_date, to_date)
    # a multi-year range must be split into more than one Azure query
    assert len(expected_periods) > 1

    result = await cost_service.query_costs(
        tag_name, tag_value, GranularityEnum.daily, from_date, to_date, [])

    total_days = (to_date.date() - from_date.date()).days + 1

    # one merged row per calendar day - nothing dropped or duplicated at the seams
    usage_dates = [row[1] for row in result.rows]
    assert len(usage_dates) == total_days
    assert len(set(usage_dates)) == total_days

    # every calendar day in the range appears exactly once (no gaps, no overlaps)
    expected_dates = set()
    day = from_date
    while day <= to_date:
        expected_dates.add(int(day.strftime("%Y%m%d")))
        day += timedelta(days=1)
    assert set(usage_dates) == expected_dates

    # the merged total equals the known per-day cost times the number of days
    total_cost = sum(row[0] for row in result.rows)
    assert total_cost == pytest.approx(daily_cost * total_days)


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_over_multiple_years_splits_queries_and_merges_results(get_resource_groups_by_tag_mock,
                                                                                     client_mock, shared_service_repo_mock,
                                                                                     workspace_repo_mock):
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    from_date = datetime(2022, 1, 1)
    to_date = datetime(2024, 6, 1)

    def __single_workspace_cost_result(*args, **kwargs):
        # rows are dated to the start of the queried range so they fall inside it
        query_definition = next(a for a in args if hasattr(a, "time_period"))
        day = query_definition.time_period.from_property.date()
        query_result = QueryResult()
        query_result.rows = [
            [10.0, int(day.strftime("%Y%m%d")), 'rg-guy22-ws-11a6',
             '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"', 'USD'],
        ]
        query_result.columns = [
            QueryColumn(name="PreTaxCost", type="Number"),
            QueryColumn(name="UsageDate", type="Number"),
            QueryColumn(name="ResourceGroup", type="String"),
            QueryColumn(name="Tag", type="String"),
            QueryColumn(name="Currency", type="String")]
        return query_result

    cost_service = CostService()
    expected_periods = __month_ranges(from_date, to_date)
    # more than one Azure query is required to cover a multi year period
    assert len(expected_periods) > 1

    client_mock.return_value.query.usage.side_effect = __single_workspace_cost_result

    cost_report = await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, from_date, to_date, workspace_repo_mock, shared_service_repo_mock)

    # one Cost Management query per split period
    assert client_mock.return_value.query.usage.call_count == len(expected_periods)

    # each split period is queried exactly once (queries may run concurrently, so
    # compare the set of periods rather than the call order). `to` is normalised to end-of-day
    # so the whole final day is included, so compare on the (from, to-date) pair.
    queried_periods = set()
    for call in client_mock.return_value.query.usage.call_args_list:
        query_definition: QueryDefinition = call[0][1]
        assert query_definition.timeframe == TimeframeType.CUSTOM
        queried_periods.add((query_definition.time_period.from_property.date(),
                             query_definition.time_period.to.date()))
    assert queried_periods == set(expected_periods)

    # results from every period are merged and summed for the workspace
    assert cost_report.workspaces[0].id == "19b7ce24-aa35-438c-adf6-37e6762911a6"
    assert cost_report.workspaces[0].costs[0].cost == 10.0 * len(expected_periods)


def __single_workspace_cost_query_result(*args, **kwargs):
    # rows are dated to the start of the queried range so they fall inside it
    query_definition = next((a for a in args if hasattr(a, "time_period")), None)
    day = query_definition.time_period.from_property.date() if query_definition \
        else datetime.now(timezone.utc).date()
    query_result = QueryResult()
    query_result.rows = [
        [10.0, int(day.strftime("%Y%m%d")), 'rg-guy22-ws-11a6',
         '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"', 'USD'],
    ]
    query_result.columns = [
        QueryColumn(name="PreTaxCost", type="Number"),
        QueryColumn(name="UsageDate", type="Number"),
        QueryColumn(name="ResourceGroup", type="String"),
        QueryColumn(name="Tag", type="String"),
        QueryColumn(name="Currency", type="String")]
    return query_result


@pytest.mark.asyncio
@patch('services.cost_service.CostManagementClient')
async def test_cost_result_cache_stores_and_expires_items(client_mock):
    cost_service = CostService()
    result = __single_workspace_cost_query_result()

    cost_service.cache_result("key", result, timedelta(hours=1))
    assert cost_service.get_cached_result("key") is result

    # an expired item is not returned and is evicted from the cache
    cost_service.cache_result("expired", result, timedelta(seconds=-1))
    assert cost_service.get_cached_result("expired") is None
    assert "expired" not in cost_service.cache


@pytest.mark.asyncio
@patch('services.cost_service.CostManagementClient')
async def test_cost_result_cache_is_bounded_and_evicts_least_recently_used(client_mock):
    cost_service = CostService()
    result = __single_workspace_cost_query_result()

    for i in range(CostService.CACHE_MAX_ITEMS):
        cost_service.cache_result(f"key{i}", result, timedelta(hours=1))

    # reading key0 makes it the most recently used, so the next insert must evict key1 instead
    assert cost_service.get_cached_result("key0") is result
    cost_service.cache_result("newest", result, timedelta(hours=1))

    # the cache is keyed per scope and day, so it must never grow without bound
    assert len(cost_service.cache) == CostService.CACHE_MAX_ITEMS
    assert cost_service.get_cached_result("key0") is result
    assert cost_service.get_cached_result("key1") is None


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_serves_repeated_requests_from_cache(get_resource_groups_by_tag_mock, client_mock,
                                                                   shared_service_repo_mock, workspace_repo_mock):
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    client_mock.return_value.query.usage.side_effect = __single_workspace_cost_query_result

    from_date = datetime(2022, 1, 1)
    to_date = datetime(2024, 6, 1)

    cost_service = CostService()
    expected_periods = __month_ranges(from_date, to_date)
    # use a multi year range so per-period caching is exercised
    assert len(expected_periods) > 1

    first_report = await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, from_date, to_date, workspace_repo_mock, shared_service_repo_mock)
    calls_after_first = client_mock.return_value.query.usage.call_count
    assert calls_after_first == len(expected_periods)

    second_report = await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, from_date, to_date, workspace_repo_mock, shared_service_repo_mock)

    # a repeated request within the cache TTL issues no further Cost Management queries
    assert client_mock.return_value.query.usage.call_count == calls_after_first
    # merging must not mutate cached period results, so totals stay identical across calls
    assert first_report.workspaces[0].costs[0].cost == 10.0 * len(expected_periods)
    assert second_report.workspaces[0].costs[0].cost == first_report.workspaces[0].costs[0].cost


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_reuses_cached_periods_for_overlapping_ranges(get_resource_groups_by_tag_mock, client_mock,
                                                                            shared_service_repo_mock, workspace_repo_mock):
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    client_mock.return_value.query.usage.side_effect = __single_workspace_cost_query_result

    from_date = datetime(2022, 1, 1)
    short_to_date = datetime(2023, 6, 1)
    long_to_date = datetime(2024, 6, 1)

    cost_service = CostService()
    short_periods = __month_ranges(from_date, short_to_date)
    long_periods = __month_ranges(from_date, long_to_date)
    # the two ranges must share at least one leading period for the cache to be reused
    assert any(period in long_periods for period in short_periods)

    await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, from_date, short_to_date, workspace_repo_mock, shared_service_repo_mock)
    calls_after_short = client_mock.return_value.query.usage.call_count
    assert calls_after_short == len(short_periods)

    await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, from_date, long_to_date, workspace_repo_mock, shared_service_repo_mock)

    # only the periods that were not already cached from the first (overlapping) request are queried
    new_periods = [period for period in long_periods if period not in short_periods]
    assert client_mock.return_value.query.usage.call_count == calls_after_short + len(new_periods)


def __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock):
    workspace_repo_mock.get_active_workspaces = AsyncMock(return_value=[
        Workspace(id='19b7ce24-aa35-438c-adf6-37e6762911a6', templateName='tre-workspace-base',
                  resourceType=ResourceType.Workspace, templateVersion="1", _etag="x",
                  properties={'display_name': 'the workspace display name1'}),
        Workspace(id='d680d6b7-d1d9-411c-9101-0793da980c81', templateName='tre-workspace-base',
                  resourceType=ResourceType.Workspace, templateVersion="1", _etag="x",
                  properties={'display_name': 'the workspace display name2'})
    ])
    #  cost reports read all (including deleted) workspaces via get_workspaces
    workspace_repo_mock.get_workspaces = workspace_repo_mock.get_active_workspaces


def __set_workspace_repo_mock_get_active_workspaces_return_value_without_display_name(workspace_repo_mock):
    workspace_repo_mock.get_active_workspaces = AsyncMock(return_value=[
        Workspace(id='19b7ce24-aa35-438c-adf6-37e6762911a6', templateName='tre-workspace-base',
                  resourceType=ResourceType.Workspace, templateVersion="1", _etag="x"),
        Workspace(id='d680d6b7-d1d9-411c-9101-0793da980c81', templateName='tre-workspace-base',
                  resourceType=ResourceType.Workspace, templateVersion="1", _etag="x")
    ])
    workspace_repo_mock.get_workspaces = workspace_repo_mock.get_active_workspaces


def __set_shared_service_repo_mock_return_value(shared_service_repo_mock):
    shared_service_repo_mock.get_active_shared_services = AsyncMock(return_value=[
        SharedService(id='848e8eb5-0df6-4d0f-9162-afd9a3fa0631', resourceType=ResourceType.SharedService,
                      templateName="tre-shared-service-firewall", templateVersion="1", _etag="x",
                      properties={'display_name': 'Shared service tre-shared-service-firewall'}),
        SharedService(id='f16d0324-9027-4448-b69b-2d48d925e6c0', resourceType=ResourceType.SharedService,
                      templateName="tre-shared-service-gitea", templateVersion="1", _etag="x",
                      properties={'display_name': 'Shared service tre-shared-service-gitea'})
    ])
    shared_service_repo_mock.get_shared_services = shared_service_repo_mock.get_active_shared_services


def __set_shared_service_repo_mock_return_value_without_display_name(shared_service_repo_mock):
    shared_service_repo_mock.get_active_shared_services = AsyncMock(return_value=[
        SharedService(id='848e8eb5-0df6-4d0f-9162-afd9a3fa0631', resourceType=ResourceType.SharedService,
                      templateName="tre-shared-service-firewall", templateVersion="1", _etag="x"),
        SharedService(id='f16d0324-9027-4448-b69b-2d48d925e6c0', resourceType=ResourceType.SharedService,
                      templateName="tre-shared-service-gitea", templateVersion="1", _etag="x")
    ])
    shared_service_repo_mock.get_shared_services = shared_service_repo_mock.get_active_shared_services


def __set_workspace_repo_mock_get_workspace_by_id_return_value(workspace_repo_mock):
    workspace_repo_mock.get_workspace_by_id = AsyncMock(return_value=Workspace(id='19b7ce24-aa35-438c-adf6-37e6762911a6',
                                                                               templateName='tre-workspace-base',
                                                                               resourceType=ResourceType.Workspace,
                                                                               templateVersion="1", _etag="x",
                                                                               properties={
                                                                                  'display_name': "workspace 1"}))


def __set_workspace_service_repo_mock_return_value(workspace_service_repo_mock):
    workspace_service_repo_mock.get_active_workspace_services_for_workspace = AsyncMock(return_value=[
        WorkspaceService(id='f8cac589-c497-4896-9fac-58e65685a20c', resourceType=ResourceType.WorkspaceService,
                         templateName="tre-service-guacamole", templateVersion="1", _etag="x",
                         properties={'display_name': 'Guacamole'}),
        WorkspaceService(id='9ad6e5d8-0bef-4b9f-91d6-ae33884883a1', resourceType=ResourceType.WorkspaceService,
                         templateName="tre-service-azureml", templateVersion="1", _etag="x",
                         properties={'display_name': 'Azure ML'})
    ])
    workspace_service_repo_mock.get_workspace_services_for_workspace = workspace_service_repo_mock.get_active_workspace_services_for_workspace


def __set_user_resource_repo_mock_return_value(user_resource_repo_mock):
    # each time 'get_user_resources_for_workspace_service' is called it will return
    # the next sub-array
    user_resource_repo_mock.get_user_resources_for_workspace_service = AsyncMock(side_effect=[
        [
            UserResource(id='09ed3e6e-fee5-41d0-937e-89644575e78c', resourceType=ResourceType.UserResource,
                         templateName="tre-user_resource_guacamole_vm", templateVersion="1", _etag="x",
                         properties={'display_name': 'VM1'}),
            UserResource(id='8ce4a294-95ae-45a9-8d48-6525ce84eb5a', resourceType=ResourceType.UserResource,
                         templateName="tre-user_resource_guacamole_vm", templateVersion="1", _etag="x",
                         properties={'display_name': 'VM2'})
        ],
        [
            UserResource(id='6ede6dc0-a1e1-40bd-92d7-3b3adcbec66d', resourceType=ResourceType.UserResource,
                         templateName="tre-user_resource_compute_instance", templateVersion="1", _etag="x",
                         properties={'display_name': 'Compute Instance 1'}),
            UserResource(id='915760d8-cf09-4cdb-b73b-815e6bfaef6f', resourceType=ResourceType.UserResource,
                         templateName="tre-user_resource_compute_instance", templateVersion="1", _etag="x",
                         properties={'display_name': 'Compute Instance 2'})
        ]

    ])


@pytest.mark.asyncio
@patch('db.repositories.user_resources.UserResourceRepository')
@patch('db.repositories.workspace_services.WorkspaceServiceRepository')
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_workspace_costs_with_granularity_none_returns_correct_workspace_cost_report(get_resource_groups_by_tag_mock,
                                                                                                     client_mock,
                                                                                                     workspace_repo_mock,
                                                                                                     workspace_services_repo_mock,
                                                                                                     user_resource_repo_mock):
    client_mock.return_value.query.usage.return_value = __get_cost_management_query_result()
    __set_workspace_repo_mock_get_workspace_by_id_return_value(workspace_repo_mock)
    __set_workspace_service_repo_mock_return_value(workspace_services_repo_mock)
    __set_user_resource_repo_mock_return_value(user_resource_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    cost_service = CostService()
    workspace_cost_report = await cost_service.query_tre_workspace_costs(
        "19b7ce24-aa35-438c-adf6-37e6762911a6", GranularityEnum.none, datetime.now(), datetime.now(),
        workspace_repo_mock,
        workspace_services_repo_mock, user_resource_repo_mock)

    assert workspace_cost_report.id == "19b7ce24-aa35-438c-adf6-37e6762911a6"
    assert workspace_cost_report.name == "workspace 1"
    assert len(workspace_cost_report.workspace_services) == 2
    assert workspace_cost_report.workspace_services[0].id == "f8cac589-c497-4896-9fac-58e65685a20c"
    assert workspace_cost_report.workspace_services[0].name == "Guacamole"
    assert len(workspace_cost_report.workspace_services[0].costs) == 1
    assert workspace_cost_report.workspace_services[0].costs[0].cost == 6.6
    assert len(workspace_cost_report.workspace_services[0].user_resources) == 2
    assert workspace_cost_report.workspace_services[0].user_resources[0].id == "09ed3e6e-fee5-41d0-937e-89644575e78c"
    assert workspace_cost_report.workspace_services[0].user_resources[0].name == "VM1"
    assert len(workspace_cost_report.workspace_services[0].user_resources[0].costs) == 1
    assert workspace_cost_report.workspace_services[0].user_resources[0].costs[0].cost == 1.3
    assert workspace_cost_report.workspace_services[0].user_resources[1].id == "8ce4a294-95ae-45a9-8d48-6525ce84eb5a"
    assert workspace_cost_report.workspace_services[0].user_resources[1].name == "VM2"
    assert len(workspace_cost_report.workspace_services[0].user_resources[1].costs) == 1
    assert workspace_cost_report.workspace_services[0].user_resources[1].costs[0].cost == 2.3

    assert workspace_cost_report.workspace_services[1].id == "9ad6e5d8-0bef-4b9f-91d6-ae33884883a1"
    assert workspace_cost_report.workspace_services[1].name == "Azure ML"
    assert len(workspace_cost_report.workspace_services[1].costs) == 1
    assert workspace_cost_report.workspace_services[1].costs[0].cost == 9.3
    assert len(workspace_cost_report.workspace_services[1].user_resources) == 2
    assert workspace_cost_report.workspace_services[1].user_resources[0].id == "6ede6dc0-a1e1-40bd-92d7-3b3adcbec66d"
    assert workspace_cost_report.workspace_services[1].user_resources[0].name == "Compute Instance 1"
    assert len(workspace_cost_report.workspace_services[1].user_resources[0].costs) == 1
    assert workspace_cost_report.workspace_services[1].user_resources[0].costs[0].cost == 5.2
    assert workspace_cost_report.workspace_services[1].user_resources[1].id == "915760d8-cf09-4cdb-b73b-815e6bfaef6f"
    assert workspace_cost_report.workspace_services[1].user_resources[1].name == "Compute Instance 2"
    assert len(workspace_cost_report.workspace_services[1].user_resources[1].costs) == 1
    assert workspace_cost_report.workspace_services[1].user_resources[1].costs[0].cost == 4.1


@pytest.mark.asyncio
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_reports_include_deleted_resources(get_resource_groups_by_tag_mock,
                                                                 client_mock,
                                                                 workspace_repo_mock,
                                                                 shared_service_repo_mock):
    # Deleted workspaces/shared services still incurred cost, so the report reads them via
    # get_workspaces / get_shared_services (which include deleted) rather than the active-only variants.
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    client_mock.return_value.query.usage.return_value = __get_cost_management_query_result()

    cost_service = CostService()
    await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, datetime.now(), datetime.now(),
        workspace_repo_mock, shared_service_repo_mock)

    workspace_repo_mock.get_workspaces.assert_awaited()
    shared_service_repo_mock.get_shared_services.assert_awaited()


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_surfaces_costs_of_resources_not_in_database(get_resource_groups_by_tag_mock,
                                                                           client_mock,
                                                                           shared_service_repo_mock,
                                                                           workspace_repo_mock):
    # Cost tagged with a workspace / shared-service id that has no database record (e.g. a
    # hard-deleted workspace or redeployed shared service) must appear in the 'unattributed'
    # bucket, while known resources' costs must not leak into it.
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)  # ids 19b7ce24, d680d6b7
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)              # ids 848e8eb5, f16d0324
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    day = int(datetime.now(timezone.utc).strftime("%Y%m%d"))
    qr = QueryResult()
    qr.columns = [QueryColumn(name="PreTaxCost", type="Number"), QueryColumn(name="UsageDate", type="Number"),
                  QueryColumn(name="ResourceGroup", type="String"),
                  QueryColumn(name="Tag", type="String"), QueryColumn(name="Currency", type="String")]
    qr.rows = [
        [1.8, day, 'rg-guy22-ws-11a6', '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"', 'USD'],  # known workspace
        [61.22, day, 'rg-guy22', '"tre_shared_service_id":"d68e1c19-gone-shared-service"', 'USD'],  # deleted shared service
        [15.5, day, 'rg-guy22-ws-gone', '"tre_workspace_id":"deleted-workspace-id"', 'USD'],  # deleted workspace
        [7.0, day, 'rg-guy22-ws-gone', '"tre_workspace_id":"deleted-workspace-id"', 'ILS'],  # deleted workspace, other currency
    ]
    client_mock.return_value.query.usage.return_value = qr

    cost_service = CostService()
    report = await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, datetime.now(), datetime.now(), workspace_repo_mock, shared_service_repo_mock)

    unattributed = {row.currency: row.cost for row in report.unattributed}
    assert unattributed["USD"] == pytest.approx(61.22 + 15.5)
    assert unattributed["ILS"] == pytest.approx(7.0)
    # the known workspace's cost is attributed to it and never counted as unattributed
    known_workspace = next(w for w in report.workspaces if w.id == "19b7ce24-aa35-438c-adf6-37e6762911a6")
    assert known_workspace.costs[0].cost == 1.8


@pytest.mark.asyncio
@patch('db.repositories.user_resources.UserResourceRepository')
@patch('db.repositories.workspace_services.WorkspaceServiceRepository')
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_workspace_costs_without_subscription_id_does_not_raise(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock,
        workspace_services_repo_mock, user_resource_repo_mock):
    # A deleted workspace whose resource group no longer exists returns no resource groups and has no
    # workspace_subscription_id property; the report must still build (previously raised KeyError -> 500)
    # and the workspace must be fetched including deleted so its historical costs are still reported.
    get_resource_groups_by_tag_mock.return_value = {}
    workspace_repo_mock.get_workspace_by_id = AsyncMock(return_value=Workspace(
        id='19b7ce24-aa35-438c-adf6-37e6762911a6', templateName='tre-workspace-base',
        resourceType=ResourceType.Workspace, templateVersion="1", _etag="x",
        properties={'display_name': 'deleted workspace'}))
    workspace_services_repo_mock.get_workspace_services_for_workspace = AsyncMock(return_value=[])
    client_mock.return_value.query.usage.return_value = QueryResult(rows=[], columns=[])

    cost_service = CostService()
    report = await cost_service.query_tre_workspace_costs(
        "19b7ce24-aa35-438c-adf6-37e6762911a6", GranularityEnum.none, datetime.now(), datetime.now(),
        workspace_repo_mock, workspace_services_repo_mock, user_resource_repo_mock)

    assert report.id == "19b7ce24-aa35-438c-adf6-37e6762911a6"
    assert report.name == "deleted workspace"
    assert workspace_repo_mock.get_workspace_by_id.await_args.kwargs.get("include_deleted") is True


@pytest.mark.asyncio
@patch('db.repositories.user_resources.UserResourceRepository')
@patch('db.repositories.workspace_services.WorkspaceServiceRepository')
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_workspace_costs_with_granularity_daily_returns_correct_workspace_cost_report(get_resource_groups_by_tag_mock,
                                                                                                      client_mock,
                                                                                                      workspace_repo_mock,
                                                                                                      workspace_services_repo_mock,
                                                                                                      user_resource_repo_mock):
    client_mock.return_value.query.usage.return_value = __set_cost_management_client_mock_query_result()
    __set_workspace_repo_mock_get_workspace_by_id_return_value(workspace_repo_mock)
    __set_workspace_service_repo_mock_return_value(workspace_services_repo_mock)
    __set_user_resource_repo_mock_return_value(user_resource_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    cost_service = CostService()
    workspace_cost_report = await cost_service.query_tre_workspace_costs(
        "19b7ce24-aa35-438c-adf6-37e6762911a6", GranularityEnum.daily,
        datetime(2022, 5, 1), datetime(2022, 5, 3),
        workspace_repo_mock,
        workspace_services_repo_mock, user_resource_repo_mock)

    assert workspace_cost_report.id == "19b7ce24-aa35-438c-adf6-37e6762911a6"
    assert workspace_cost_report.name == "workspace 1"
    assert len(workspace_cost_report.workspace_services) == 2
    assert workspace_cost_report.workspace_services[0].id == "f8cac589-c497-4896-9fac-58e65685a20c"
    assert workspace_cost_report.workspace_services[0].name == "Guacamole"
    assert len(workspace_cost_report.workspace_services[0].costs) == 3
    assert workspace_cost_report.workspace_services[0].costs[0].cost == 14.8
    assert len(workspace_cost_report.workspace_services[0].user_resources) == 2
    assert workspace_cost_report.workspace_services[0].user_resources[0].id == "09ed3e6e-fee5-41d0-937e-89644575e78c"
    assert workspace_cost_report.workspace_services[0].user_resources[0].name == "VM1"
    assert len(workspace_cost_report.workspace_services[0].user_resources[0].costs) == 4
    assert workspace_cost_report.workspace_services[0].user_resources[0].costs[0].cost == 114.8
    assert workspace_cost_report.workspace_services[0].user_resources[0].costs[1].cost == 115.8
    assert workspace_cost_report.workspace_services[0].user_resources[0].costs[2].cost == 216.8
    assert workspace_cost_report.workspace_services[0].user_resources[0].costs[2].currency == "ILS"
    assert workspace_cost_report.workspace_services[0].user_resources[0].costs[3].cost == 116.8
    assert workspace_cost_report.workspace_services[0].user_resources[0].costs[3].currency == "USD"

    assert workspace_cost_report.workspace_services[0].user_resources[1].id == "8ce4a294-95ae-45a9-8d48-6525ce84eb5a"
    assert workspace_cost_report.workspace_services[0].user_resources[1].name == "VM2"
    assert len(workspace_cost_report.workspace_services[0].user_resources[1].costs) == 3
    assert workspace_cost_report.workspace_services[0].user_resources[1].costs[0].cost == 164.8

    assert workspace_cost_report.workspace_services[1].id == "9ad6e5d8-0bef-4b9f-91d6-ae33884883a1"
    assert workspace_cost_report.workspace_services[1].name == "Azure ML"
    assert len(workspace_cost_report.workspace_services[1].costs) == 3
    assert workspace_cost_report.workspace_services[1].costs[0].cost == 24.8
    assert len(workspace_cost_report.workspace_services[1].user_resources) == 2
    assert workspace_cost_report.workspace_services[1].user_resources[0].id == "6ede6dc0-a1e1-40bd-92d7-3b3adcbec66d"
    assert workspace_cost_report.workspace_services[1].user_resources[0].name == "Compute Instance 1"
    assert len(workspace_cost_report.workspace_services[1].user_resources[0].costs) == 3
    assert workspace_cost_report.workspace_services[1].user_resources[0].costs[0].cost == 164.8
    assert workspace_cost_report.workspace_services[1].user_resources[1].id == "915760d8-cf09-4cdb-b73b-815e6bfaef6f"
    assert workspace_cost_report.workspace_services[1].user_resources[1].name == "Compute Instance 2"
    assert len(workspace_cost_report.workspace_services[1].user_resources[1].costs) == 3
    assert workspace_cost_report.workspace_services[1].user_resources[1].costs[0].cost == 168.8


def __get_workspace_daily_source_query_result():
    # Monthly workspace reports are derived from Daily data, so Cost Management is queried at
    # Daily granularity across the workspace, its services and its user resources.
    query_result = QueryResult()
    query_result.columns = [
        QueryColumn(name="PreTaxCost", type="Number"),
        QueryColumn(name="UsageDate", type="Number"),
        QueryColumn(name="ResourceGroup", type="String"),
        QueryColumn(name="Tag", type="String"),
        QueryColumn(name="Currency", type="String")]
    query_result.rows = [
        # workspace itself: May = 10 + 12 = 22, June = 20
        [10.0, 20260501, 'rg-ws', '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"', 'USD'],
        [12.0, 20260502, 'rg-ws', '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"', 'USD'],
        [20.0, 20260601, 'rg-ws', '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"', 'USD'],
        # workspace service Guacamole: May = 3.0 + 3.6 = 6.6, June = 4.0
        [3.0, 20260501, 'rg-ws', '"tre_workspace_service_id":"f8cac589-c497-4896-9fac-58e65685a20c"', 'USD'],
        [3.6, 20260502, 'rg-ws', '"tre_workspace_service_id":"f8cac589-c497-4896-9fac-58e65685a20c"', 'USD'],
        [4.0, 20260601, 'rg-ws', '"tre_workspace_service_id":"f8cac589-c497-4896-9fac-58e65685a20c"', 'USD'],
        # user resource VM1: May = 1.0 + 0.3 = 1.3, June = 2.0
        [1.0, 20260501, 'rg-ws', '"tre_user_resource_id":"09ed3e6e-fee5-41d0-937e-89644575e78c"', 'USD'],
        [0.3, 20260502, 'rg-ws', '"tre_user_resource_id":"09ed3e6e-fee5-41d0-937e-89644575e78c"', 'USD'],
        [2.0, 20260601, 'rg-ws', '"tre_user_resource_id":"09ed3e6e-fee5-41d0-937e-89644575e78c"', 'USD'],
    ]
    return query_result


@pytest.mark.asyncio
@patch('db.repositories.user_resources.UserResourceRepository')
@patch('db.repositories.workspace_services.WorkspaceServiceRepository')
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
# CostService is lru_cached which creates a wrapper method
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_workspace_costs_with_granularity_monthly_aggregates_daily(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock,
        workspace_services_repo_mock, user_resource_repo_mock):
    client_mock.return_value.query.usage.side_effect = __daily_result_within_queried_range(
        __get_workspace_daily_source_query_result())
    __set_workspace_repo_mock_get_workspace_by_id_return_value(workspace_repo_mock)
    __set_workspace_service_repo_mock_return_value(workspace_services_repo_mock)
    __set_user_resource_repo_mock_return_value(user_resource_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    cost_service = CostService()
    report = await cost_service.query_tre_workspace_costs(
        "19b7ce24-aa35-438c-adf6-37e6762911a6", GranularityEnum.monthly,
        datetime(2026, 5, 1), datetime(2026, 6, 1),
        workspace_repo_mock, workspace_services_repo_mock, user_resource_repo_mock)

    # Monthly is queried at Daily granularity from Cost Management, then aggregated per month at
    # every level of the workspace hierarchy.
    assert client_mock.return_value.query.usage.call_args[0][1].dataset.granularity == GranularityEnum.daily

    # workspace-level costs rolled up per month
    ws_costs = {c.date: c.cost for c in report.costs}
    assert ws_costs[date(2026, 5, 1)] == 22.0
    assert ws_costs[date(2026, 6, 1)] == 20.0

    # workspace service (Guacamole) rolled up per month
    guacamole = next(s for s in report.workspace_services if s.id == "f8cac589-c497-4896-9fac-58e65685a20c")
    guacamole_costs = {c.date: c.cost for c in guacamole.costs}
    assert guacamole_costs[date(2026, 5, 1)] == pytest.approx(6.6)
    assert guacamole_costs[date(2026, 6, 1)] == 4.0

    # user resource (VM1) under that service rolled up per month
    vm1 = next(u for u in guacamole.user_resources if u.id == "09ed3e6e-fee5-41d0-937e-89644575e78c")
    vm1_costs = {c.date: c.cost for c in vm1.costs}
    assert vm1_costs[date(2026, 5, 1)] == pytest.approx(1.3)
    assert vm1_costs[date(2026, 6, 1)] == 2.0


def __get_cost_management_query_result(usage_date=None):
    # Cost data is always queried from Cost Management at Daily granularity; ungranular and
    # Monthly reports are derived from those days, so the mocked result is Daily-shaped.
    usage_date = usage_date or datetime.now(timezone.utc).date()
    day = int(usage_date.strftime("%Y%m%d"))
    query_result = QueryResult()
    query_result.rows = [
        [37.6, day, 'rg-guy22', '"tre_core_service_id":"guy22"', 'USD'],
        [44.5, day, 'rg-guy22', '"tre_id":"guy22"', 'USD'],
        [6.8, day, 'rg-guy22', '"tre_shared_service_id":"848e8eb5-0df6-4d0f-9162-afd9a3fa0631"', 'USD'],
        [4.8, day, 'rg-guy22', '"tre_shared_service_id":"f16d0324-9027-4448-b69b-2d48d925e6c0"', 'USD'],
        [1.8, day, 'rg-guy22-ws-11a6', '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"', 'USD'],
        [2.8, day, 'rg-guy22-ws-0c81', '"tre_workspace_id":"d680d6b7-d1d9-411c-9101-0793da980c81"', 'USD'],
        [5.8, day, 'rg-guy22-ws-0c81', '"tre_workspace_id":"d680d6b7-d1d9-411c-9101-0793da980c81"', 'ILS'],
        [6.6, day, 'rg-guy22-ws-11a6', '"tre_workspace_service_id":"f8cac589-c497-4896-9fac-58e65685a20c"', 'USD'],
        [9.3, day, 'rg-guy22-ws-0c81', '"tre_workspace_service_id":"9ad6e5d8-0bef-4b9f-91d6-ae33884883a1"', 'USD'],
        [1.3, day, 'rg-guy22-ws-11a6', '"tre_user_resource_id":"09ed3e6e-fee5-41d0-937e-89644575e78c"', 'USD'],
        [2.3, day, 'rg-guy22-ws-0c81', '"tre_user_resource_id":"8ce4a294-95ae-45a9-8d48-6525ce84eb5a"', 'USD'],
        [5.2, day, 'rg-guy22-ws-11a6', '"tre_user_resource_id":"6ede6dc0-a1e1-40bd-92d7-3b3adcbec66d"', 'USD'],
        [4.1, day, 'rg-guy22-ws-11a6', '"tre_user_resource_id":"915760d8-cf09-4cdb-b73b-815e6bfaef6f"', 'USD'],
    ]
    query_result.columns = [QueryColumn(name="PreTaxCost", type="Number"),
                            QueryColumn(name="UsageDate", type="Number"),
                            QueryColumn(name="ResourceGroup", type="String"),
                            QueryColumn(name="Tag", type="String"),
                            QueryColumn(name="Currency", type="String")]
    return query_result


def __set_cost_management_client_mock_query_result():
    query_result = QueryResult()
    query_result.rows = [
        [31.6, 20220501, 'rg-guy22', '"tre_core_service_id":"guy22"', 'USD'],
        [32.6, 20220502, 'rg-guy22', '"tre_core_service_id":"guy22"', 'USD'],
        [33.6, 20220503, 'rg-guy22', '"tre_core_service_id":"guy22"', 'USD'],

        [44.5, 20220501, 'rg-guy22', '"tre_id":"guy22"', 'USD'],
        [44.5, 20220502, 'rg-guy22', '"tre_id":"guy22"', 'USD'],
        [44.5, 20220503, 'rg-guy22', '"tre_id":"guy22"', 'USD'],

        [3.8, 20220501, 'rg-guy22', '"tre_shared_service_id":"848e8eb5-0df6-4d0f-9162-afd9a3fa0631"', 'USD'],
        [4.8, 20220502, 'rg-guy22', '"tre_shared_service_id":"848e8eb5-0df6-4d0f-9162-afd9a3fa0631"', 'USD'],
        [5.8, 20220503, 'rg-guy22', '"tre_shared_service_id":"848e8eb5-0df6-4d0f-9162-afd9a3fa0631"', 'USD'],

        [2.8, 20220501, 'rg-guy22', '"tre_shared_service_id":"f16d0324-9027-4448-b69b-2d48d925e6c0"', 'USD'],
        [3.8, 20220502, 'rg-guy22', '"tre_shared_service_id":"f16d0324-9027-4448-b69b-2d48d925e6c0"', 'USD'],
        [4.8, 20220503, 'rg-guy22', '"tre_shared_service_id":"f16d0324-9027-4448-b69b-2d48d925e6c0"', 'USD'],

        [1.8, 20220501, 'rg-guy22-ws-11a6', '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"', 'USD'],
        [2.8, 20220502, 'rg-guy22-ws-11a6', '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"', 'USD'],
        [3.8, 20220503, 'rg-guy22-ws-11a6', '"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"', 'USD'],

        [4.8, 20220501, 'rg-guy22-ws-0c81', '"tre_workspace_id":"d680d6b7-d1d9-411c-9101-0793da980c81"', 'USD'],
        [5.8, 20220502, 'rg-guy22-ws-0c81', '"tre_workspace_id":"d680d6b7-d1d9-411c-9101-0793da980c81"', 'USD'],
        [6.8, 20220503, 'rg-guy22-ws-0c81', '"tre_workspace_id":"d680d6b7-d1d9-411c-9101-0793da980c81"', 'USD'],
        [16.8, 20220503, 'rg-guy22-ws-0c81', '"tre_workspace_id":"d680d6b7-d1d9-411c-9101-0793da980c81"', 'ILS'],

        [14.8, 20220501, 'rg-guy22-ws-11a6', '"tre_workspace_service_id":"f8cac589-c497-4896-9fac-58e65685a20c"', 'USD'],
        [15.8, 20220502, 'rg-guy22-ws-11a6', '"tre_workspace_service_id":"f8cac589-c497-4896-9fac-58e65685a20c"', 'USD'],
        [16.8, 20220503, 'rg-guy22-ws-11a6', '"tre_workspace_service_id":"f8cac589-c497-4896-9fac-58e65685a20c"', 'USD'],

        [24.8, 20220501, 'rg-guy22-ws-0c81', '"tre_workspace_service_id":"9ad6e5d8-0bef-4b9f-91d6-ae33884883a1"', 'USD'],
        [25.8, 20220502, 'rg-guy22-ws-0c81', '"tre_workspace_service_id":"9ad6e5d8-0bef-4b9f-91d6-ae33884883a1"', 'USD'],
        [26.8, 20220503, 'rg-guy22-ws-0c81', '"tre_workspace_service_id":"9ad6e5d8-0bef-4b9f-91d6-ae33884883a1"', 'USD'],

        [114.8, 20220501, 'rg-guy22-ws-11a6', '"tre_user_resource_id":"09ed3e6e-fee5-41d0-937e-89644575e78c"', 'USD'],
        [115.8, 20220502, 'rg-guy22-ws-11a6', '"tre_user_resource_id":"09ed3e6e-fee5-41d0-937e-89644575e78c"', 'USD'],
        [116.8, 20220503, 'rg-guy22-ws-11a6', '"tre_user_resource_id":"09ed3e6e-fee5-41d0-937e-89644575e78c"', 'USD'],
        [216.8, 20220503, 'rg-guy22-ws-11a6', '"tre_user_resource_id":"09ed3e6e-fee5-41d0-937e-89644575e78c"', 'ILS'],

        [164.8, 20220501, 'rg-guy22-ws-0c81', '"tre_user_resource_id":"8ce4a294-95ae-45a9-8d48-6525ce84eb5a"', 'USD'],
        [165.8, 20220502, 'rg-guy22-ws-0c81', '"tre_user_resource_id":"8ce4a294-95ae-45a9-8d48-6525ce84eb5a"', 'USD'],
        [166.8, 20220503, 'rg-guy22-ws-0c81', '"tre_user_resource_id":"8ce4a294-95ae-45a9-8d48-6525ce84eb5a"', 'USD'],

        [164.8, 20220501, 'rg-guy22-ws-0c81', '"tre_user_resource_id":"6ede6dc0-a1e1-40bd-92d7-3b3adcbec66d"', 'USD'],
        [165.8, 20220502, 'rg-guy22-ws-0c81', '"tre_user_resource_id":"6ede6dc0-a1e1-40bd-92d7-3b3adcbec66d"', 'USD'],
        [166.8, 20220503, 'rg-guy22-ws-0c81', '"tre_user_resource_id":"6ede6dc0-a1e1-40bd-92d7-3b3adcbec66d"', 'USD'],

        [168.8, 20220501, 'rg-guy22-ws-0c81', '"tre_user_resource_id":"915760d8-cf09-4cdb-b73b-815e6bfaef6f"', 'USD'],
        [168.8, 20220502, 'rg-guy22-ws-0c81', '"tre_user_resource_id":"915760d8-cf09-4cdb-b73b-815e6bfaef6f"', 'USD'],
        [168.8, 20220503, 'rg-guy22-ws-0c81', '"tre_user_resource_id":"915760d8-cf09-4cdb-b73b-815e6bfaef6f"', 'USD']
    ]

    query_result.columns = [QueryColumn(name="PreTaxCost", type="Number"),
                            QueryColumn(name="UsageDate", type="DateTime"),
                            QueryColumn(name="ResourceGroup", type="String"),
                            QueryColumn(name="Tag", type="String"),
                            QueryColumn(name="Currency", type="String")]

    return query_result


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_subscription_id_includes_default_and_workspace_ids(get_resource_groups_by_tag_mock, client_mock, shared_service_repo_mock, workspace_repo_mock):
    from services import cost_service as cs
    cs.config.SUBSCRIPTION_ID = "default-sub-id"

    # Workspace with and without subscription id
    workspace_repo_mock.get_active_workspaces = AsyncMock(return_value=[
        Workspace(id='ws1', templateName='t1', resourceType=ResourceType.Workspace, templateVersion="1", _etag="x", properties={}),
        Workspace(id='ws2', templateName='t2', resourceType=ResourceType.Workspace, templateVersion="1", _etag="x", properties={"workspace_subscription_id": "sub-2"}),
        Workspace(id='ws3', templateName='t3', resourceType=ResourceType.Workspace, templateVersion="1", _etag="x", properties={"workspace_subscription_id": "sub-3"}),
        Workspace(id='ws4', templateName='t4', resourceType=ResourceType.Workspace, templateVersion="1", _etag="x", properties={"workspace_subscription_id": "sub-2"}),  # duplicate
    ])
    workspace_repo_mock.get_workspaces = workspace_repo_mock.get_active_workspaces
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    get_resource_groups_by_tag_mock.return_value = {}
    client_mock.return_value.query.usage.return_value = QueryResult(rows=[], columns=[])

    cost_service = CostService()
    await cost_service.query_tre_costs(
        "treid", GranularityEnum.none, datetime.now(), datetime.now(), workspace_repo_mock, shared_service_repo_mock)

    # Collect all subscription_ids used in get_resource_groups_by_tag calls
    called_sub_ids = set(call.args[2] for call in get_resource_groups_by_tag_mock.call_args_list)
    # Should include default and both unique workspace ids
    assert called_sub_ids == {"default-sub-id", "sub-2", "sub-3"}


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_subscription_id_skips_workspaces_without_id(get_resource_groups_by_tag_mock, client_mock, shared_service_repo_mock, workspace_repo_mock):
    from services import cost_service as cs
    cs.config.SUBSCRIPTION_ID = "default-sub-id"

    workspace_repo_mock.get_active_workspaces = AsyncMock(return_value=[
        Workspace(id='ws1', templateName='t1', resourceType=ResourceType.Workspace, templateVersion="1", _etag="x", properties={}),
        Workspace(id='ws2', templateName='t2', resourceType=ResourceType.Workspace, templateVersion="1", _etag="x", properties={}),
    ])
    workspace_repo_mock.get_workspaces = workspace_repo_mock.get_active_workspaces
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    get_resource_groups_by_tag_mock.return_value = {}
    client_mock.return_value.query.usage.return_value = QueryResult(rows=[], columns=[])

    cost_service = CostService()
    await cost_service.query_tre_costs(
        "treid", GranularityEnum.none, datetime.now(), datetime.now(), workspace_repo_mock, shared_service_repo_mock)

    called_sub_ids = set(call.args[2] for call in get_resource_groups_by_tag_mock.call_args_list)
    assert called_sub_ids == {"default-sub-id"}


def __get_costs_repo_mock(persisted=None):
    costs_repo = AsyncMock(spec=CostsRepository)
    costs_repo.get_cost_days.return_value = persisted or []
    # the real builder so persisted documents can be asserted on
    costs_repo.build_cost_day.side_effect = CostsRepository.build_cost_day
    costs_repo.save_cost_days.return_value = None
    return costs_repo, PersistedCostDay


def __persisted_day(usage_date, rows, final=True, scope="/subscriptions/sub-id",
                    tag_name="tre_id", tag_value="guy22"):
    return PersistedCostDay(
        id=usage_date, partitionKey=f"guy22/{usage_date[:7]}", tre_id="guy22", scope=scope,
        tag_name=tag_name, tag_value=tag_value, usage_date=usage_date,
        rows=rows, final=final, collected_at="2022-06-01T00:00:00+00:00")


def __persisted_days(costs_repo):
    """Every day document written, in write order."""
    return [day for call in costs_repo.save_cost_days.await_args_list for day in call.args[0]]


def __all_persisted_rows(costs_repo):
    """Every row written across the per-day documents, in write order."""
    return [row for day in __persisted_days(costs_repo) for row in day.rows]


def __month_ranges(from_date, to_date):
    """The month-aligned day ranges the service queries when no day is already collected."""
    ranges = []
    day = from_date.date()
    last = to_date.date()
    while day <= last:
        month_end = (day.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        end = min(month_end, last)
        ranges.append((day, end))
        day = end + timedelta(days=1)
    return ranges


def __daily_result_within_queried_range(source):
    """Return a query.usage side effect that only returns days inside the queried range.

    Cost Management only ever returns days within the requested period; the service queries
    missing days in month-aligned batches, so a fixture returned wholesale would be counted
    once per batch.
    """
    def __side_effect(*args, **kwargs):
        query_definition = next(a for a in args if hasattr(a, "time_period"))
        start = int(query_definition.time_period.from_property.date().strftime("%Y%m%d"))
        end = int(query_definition.time_period.to.date().strftime("%Y%m%d"))
        query_result = QueryResult()
        query_result.columns = source.columns
        query_result.rows = [row for row in source.rows if start <= row[1] <= end]
        return query_result
    return __side_effect


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_persists_live_result_to_collection(
        get_resource_groups_by_tag_mock, client_mock, shared_service_repo_mock, workspace_repo_mock):
    client_mock.return_value.query.usage.return_value = __get_cost_management_query_result()
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    cost_service = CostService()
    await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, datetime.now(), datetime.now(),
        workspace_repo_mock, shared_service_repo_mock, costs_repo)

    # collection was consulted and then populated on the miss
    costs_repo.get_cost_days.assert_awaited()
    costs_repo.save_cost_days.assert_awaited()


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_reads_from_collection_without_calling_cost_management(
        get_resource_groups_by_tag_mock, client_mock, shared_service_repo_mock, workspace_repo_mock):
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    # every day of the requested range is already collected, so nothing needs a live query
    today = datetime.now(timezone.utc).date()
    persisted = [__persisted_day(
        today.isoformat(),
        [[37.6, int(today.strftime("%Y%m%d")), 'rg-guy22', '"tre_core_service_id":"guy22"', 'USD']])]
    costs_repo, _ = __get_costs_repo_mock(persisted=persisted)

    cost_service = CostService()
    cost_report = await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, datetime.now(), datetime.now(),
        workspace_repo_mock, shared_service_repo_mock, costs_repo)

    # served from the collection; no live query, no write
    client_mock.return_value.query.usage.assert_not_called()
    costs_repo.save_cost_days.assert_not_awaited()
    assert cost_report.core_services[0].cost == 37.6


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_ignores_non_final_collection_period_and_queries_live(
        get_resource_groups_by_tag_mock, client_mock, shared_service_repo_mock, workspace_repo_mock):
    # A still-settling (non-final) day is never returned by the collection, so it is re-queried
    # live and reports never return stale figures.
    client_mock.return_value.query.usage.return_value = __get_cost_management_query_result()
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    costs_repo, _ = __get_costs_repo_mock(persisted=[])

    cost_service = CostService()
    cost_report = await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, datetime.now(), datetime.now(),
        workspace_repo_mock, shared_service_repo_mock, costs_repo)

    # the still-settling day is queried live and its result used and written back
    client_mock.return_value.query.usage.assert_called()
    costs_repo.save_cost_days.assert_awaited()
    assert cost_report.core_services[0].cost == 37.6


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_refresh_costs_persists_each_period(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    client_mock.return_value.query.usage.return_value = __get_cost_management_query_result()
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    cost_service = CostService()
    collected = await cost_service.refresh_costs(
        "guy22", GranularityEnum.daily, datetime(2022, 5, 1), datetime(2022, 5, 31),
        workspace_repo_mock, costs_repo)

    assert collected["collected_periods"] >= 1
    costs_repo.save_cost_days.assert_awaited()


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_refresh_costs_marks_completed_month_as_final(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    client_mock.return_value.query.usage.return_value = __get_cost_management_query_result()
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    # a month whose data settled long ago is complete and immutable
    settled_month_start = datetime(2022, 5, 1)
    settled_month_end = datetime(2022, 5, 31)

    cost_service = CostService()
    await cost_service.refresh_costs(
        "guy22", GranularityEnum.daily, settled_month_start, settled_month_end,
        workspace_repo_mock, costs_repo)

    assert __persisted_days(costs_repo)[-1].final is True


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_refresh_costs_does_not_finalise_still_settling_period(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    # A period whose last day is still inside the settling window must be stored as NOT final, so
    # idempotent refresh keeps re-querying it until Azure finishes re-rating. Freezing it early
    # would persist partially-settled data that reads would then serve (and under-report).
    client_mock.return_value.query.usage.return_value = __get_cost_management_query_result()
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    today = datetime.now()
    recent_start = today - timedelta(days=3)
    recent_end = today - timedelta(days=1)  # ended yesterday - still within the settling window

    cost_service = CostService()
    await cost_service.refresh_costs(
        "guy22", GranularityEnum.daily, recent_start, recent_end, workspace_repo_mock, costs_repo)

    assert __persisted_days(costs_repo)[-1].final is False


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_refresh_costs_month_to_date_is_not_final(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    client_mock.return_value.query.usage.return_value = __get_cost_management_query_result()
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    cost_service = CostService()
    # no dates => month-to-date, still settling, must never be marked final
    collected = await cost_service.refresh_costs(
        "guy22", GranularityEnum.daily, None, None, workspace_repo_mock, costs_repo)

    # one document per day of the month so far, for each of the 3 scopes
    # (the TRE-wide tag plus each of the 2 active workspaces)
    days_so_far = datetime.now(timezone.utc).day
    assert collected["collected_periods"] == days_so_far * 3
    # the most recent days are still settling, so the last written day is not final
    assert __persisted_days(costs_repo)[-1].final is False


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_refresh_costs_multi_year_persists_one_document_per_day(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    client_mock.return_value.query.usage.return_value = __get_cost_management_query_result()
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    from_date = datetime(2022, 1, 1)
    to_date = datetime(2025, 1, 1)

    cost_service = CostService()
    expected_days = (to_date.date() - from_date.date()).days + 1

    collected = await cost_service.refresh_costs(
        "guy22", GranularityEnum.daily, from_date, to_date, workspace_repo_mock, costs_repo)

    # every day is collected once per scope: the TRE-wide tag plus each of the 2 active
    # workspaces (so the workspace report can also be served from the collection).
    expected_scopes = 3
    assert collected["collected_periods"] == expected_days * expected_scopes
    assert len(__persisted_days(costs_repo)) == expected_days * expected_scopes


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_refresh_costs_skips_already_final_days(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    # Already-finalised days are reused from the collection: no Cost Management call and no
    # re-write, so repeated/backfill refreshes are idempotent and don't re-hit Azure.
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    from_date = datetime(2022, 5, 1)
    to_date = datetime(2022, 5, 31)
    days = [(from_date.date() + timedelta(days=offset)) for offset in range(31)]
    persisted = [__persisted_day(
        day.isoformat(),
        [[10.0, int(day.strftime("%Y%m%d")), 'rg-guy22', '"tre_id":"guy22"', 'USD'],
         [11.0, int(day.strftime("%Y%m%d")), 'rg-guy22', '"tre_id":"guy22"', 'USD']]) for day in days]
    costs_repo, _ = __get_costs_repo_mock(persisted=persisted)

    cost_service = CostService()
    result = await cost_service.refresh_costs(
        "guy22", GranularityEnum.daily, from_date, to_date,
        workspace_repo_mock, costs_repo)

    # existing final days reused: no Azure query, no re-write
    client_mock.return_value.query.usage.assert_not_called()
    costs_repo.save_cost_days.assert_not_awaited()
    # total_rows still reflects the existing days so the backfill sees the month has data;
    # 31 days per scope (TRE-wide tag plus each of the 2 active workspaces).
    assert result["collected_periods"] == 31 * 3
    assert result["total_rows"] == 2 * 31 * 3


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_refresh_costs_reports_zero_rows_for_empty_period(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    # A period Azure returns with no rows reports total_rows == 0 so the history backfill can
    # tell it has walked back past the start of the data and stop.
    empty = QueryResult()
    empty.columns = [QueryColumn(name="PreTaxCost", type="Number"),
                     QueryColumn(name="UsageDate", type="Number"),
                     QueryColumn(name="ResourceGroup", type="String"),
                     QueryColumn(name="Tag", type="String"),
                     QueryColumn(name="Currency", type="String")]
    empty.rows = []
    client_mock.return_value.query.usage.return_value = empty
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    cost_service = CostService()
    result = await cost_service.refresh_costs(
        "guy22", GranularityEnum.daily, datetime(2019, 1, 1), datetime(2019, 1, 31),
        workspace_repo_mock, costs_repo)

    # one empty document per day per scope (TRE-wide tag plus each of the 2 active workspaces)
    assert result["collected_periods"] == 31 * 3
    assert result["total_rows"] == 0


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_refresh_costs_collects_per_workspace_tag(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    # The workspace cost report queries the tre_workspace_id tag, which is a different collection
    # key from the TRE-wide tre_id tag. refresh_costs must persist both so the workspace endpoint
    # is served from the collection rather than always falling back to a live Azure query.
    client_mock.return_value.query.usage.return_value = __get_cost_management_query_result()
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    cost_service = CostService()
    await cost_service.refresh_costs(
        "guy22", GranularityEnum.daily, datetime(2022, 5, 1), datetime(2022, 5, 31),
        workspace_repo_mock, costs_repo)

    persisted_tags = {(day.tag_name, day.tag_value) for day in __persisted_days(costs_repo)}
    # the TRE-wide scope plus one scope per active workspace were all persisted
    assert ("tre_id", "guy22") in persisted_tags
    assert ("tre_workspace_id", "19b7ce24-aa35-438c-adf6-37e6762911a6") in persisted_tags
    assert ("tre_workspace_id", "d680d6b7-d1d9-411c-9101-0793da980c81") in persisted_tags


@patch('services.cost_service.CostManagementClient')
async def test_is_day_final_true_only_after_settling_window(client_mock):
    cost_service = CostService()
    today = datetime.now(timezone.utc).date()
    settling_days = CostService.COST_DATA_SETTLING_DAYS

    # a day still inside the settling window keeps being re-rated by Azure, so it is not final
    assert cost_service._CostService__is_day_final(today) is False
    assert cost_service._CostService__is_day_final(today - timedelta(days=settling_days)) is False
    # a future day is not final
    assert cost_service._CostService__is_day_final(today + timedelta(days=40)) is False
    # a day safely past the settling window is final
    assert cost_service._CostService__is_day_final(today - timedelta(days=settling_days + 1)) is True


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_persists_completed_period_as_final(
        get_resource_groups_by_tag_mock, client_mock, shared_service_repo_mock, workspace_repo_mock):
    client_mock.return_value.query.usage.return_value = __get_cost_management_query_result()
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    settled_month_start = datetime(2022, 5, 1)
    settled_month_end = datetime(2022, 5, 31)

    cost_service = CostService()
    await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, settled_month_start, settled_month_end,
        workspace_repo_mock, shared_service_repo_mock, costs_repo)

    # a completed period queried live is written back to the collection as final
    costs_repo.save_cost_days.assert_awaited()
    assert __persisted_days(costs_repo)[-1].final is True


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('db.repositories.shared_services.SharedServiceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_query_tre_costs_without_repo_still_queries_live(
        get_resource_groups_by_tag_mock, client_mock, shared_service_repo_mock, workspace_repo_mock):
    # costs_repo is optional; omitting it must not break the live query path
    client_mock.return_value.query.usage.return_value = __get_cost_management_query_result()
    __set_shared_service_repo_mock_return_value(shared_service_repo_mock)
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    cost_service = CostService()
    cost_report = await cost_service.query_tre_costs(
        "guy22", GranularityEnum.none, None, None, workspace_repo_mock, shared_service_repo_mock)

    client_mock.return_value.query.usage.assert_called()
    assert cost_report.core_services[0].cost == 37.6


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_ingest_export_costs_persists_one_period_per_scope(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    cost_service = CostService()
    collected = await cost_service.ingest_export_costs(
        "guy22", GranularityEnum.daily, datetime(2022, 5, 1), datetime(2022, 5, 31),
        __exported_rows(), workspace_repo_mock, costs_repo)

    # the TRE-wide scope plus one per active workspace
    assert collected["collected_periods"] == 3
    costs_repo.save_cost_days.assert_awaited()
    # a closed month exported from Cost Management is immutable
    assert __persisted_days(costs_repo)[-1].final is True
    # no Cost Management *query* is issued - the data came from the export
    client_mock.return_value.query.usage.assert_not_called()


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_ingest_export_costs_only_attributes_rows_to_the_exported_subscription(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    # An export covers exactly one subscription. Writing its rows to every subscription the TRE
    # spans would count the exported subscription's costs once per subscription.
    workspace_repo_mock.get_active_workspaces = AsyncMock(return_value=[
        Workspace(id='ws-elsewhere', templateName='t', resourceType=ResourceType.Workspace,
                  templateVersion="1", _etag="x",
                  properties={"workspace_subscription_id": "sub-2"}),
    ])
    workspace_repo_mock.get_workspaces = workspace_repo_mock.get_active_workspaces
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    cost_service = CostService()
    await cost_service.ingest_export_costs(
        "guy22", GranularityEnum.daily, datetime(2022, 5, 1), datetime(2022, 5, 31),
        __exported_rows(), workspace_repo_mock, costs_repo, "sub-2")

    tre_wide_scopes = {day.scope for day in __persisted_days(costs_repo) if day.tag_name == "tre_id"}
    assert tre_wide_scopes == {"/subscriptions/sub-2"}


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_ingest_export_costs_defaults_to_the_core_subscription(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    from services import cost_service as cs
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    cost_service = CostService()
    await cost_service.ingest_export_costs(
        "guy22", GranularityEnum.daily, datetime(2022, 5, 1), datetime(2022, 5, 31),
        __exported_rows(), workspace_repo_mock, costs_repo)

    tre_wide_scopes = {day.scope for day in __persisted_days(costs_repo) if day.tag_name == "tre_id"}
    assert tre_wide_scopes == {"/subscriptions/{}".format(cs.config.SUBSCRIPTION_ID)}


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
async def test_get_subscription_ids_lists_the_core_subscription_first(client_mock, workspace_repo_mock):
    # the Cost Processor runs one export per subscription and asks the API which ones exist
    from services import cost_service as cs
    original_subscription_id = cs.config.SUBSCRIPTION_ID
    cs.config.SUBSCRIPTION_ID = "core-sub"
    workspace_repo_mock.get_workspaces = AsyncMock(return_value=[
        Workspace(id='ws1', templateName='t', resourceType=ResourceType.Workspace,
                  templateVersion="1", _etag="x", properties={}),
        Workspace(id='ws2', templateName='t', resourceType=ResourceType.Workspace,
                  templateVersion="1", _etag="x", properties={"workspace_subscription_id": "sub-2"}),
        Workspace(id='ws3', templateName='t', resourceType=ResourceType.Workspace,
                  templateVersion="1", _etag="x", properties={"workspace_subscription_id": "sub-2"}),
    ])

    try:
        cost_service = CostService()
        subscription_ids = await cost_service.get_subscription_ids(workspace_repo_mock)
    finally:
        cs.config.SUBSCRIPTION_ID = original_subscription_id

    assert subscription_ids == ["core-sub", "sub-2"]


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_ingest_export_costs_attributes_each_row_to_its_own_workspace_scope(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    # Exported rows are indexed once and then narrowed per scope rather than rescanned, so
    # assert the narrowing still finds a workspace's rows wherever they live and drops the rest.
    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    workspace_id = "19b7ce24-aa35-438c-adf6-37e6762911a6"
    rows = __exported_rows() + [
        # tagged for the workspace but in a resource group the scope doesn't list (e.g. a
        # managed group, or one already deleted) - found via the tag index
        ExportedCostRow(date=20220501, resource_group='rg-managed-by-azure',
                        tag=f'"tre_workspace_id":"{workspace_id}"', cost=5.0, currency='USD'),
        ExportedCostRow(date=20220501, resource_group='rg-someone-else', tag='"owner":"other"',
                        cost=99.0, currency='USD')]

    cost_service = CostService()
    await cost_service.ingest_export_costs(
        "guy22", GranularityEnum.daily, datetime(2022, 5, 1), datetime(2022, 5, 31),
        rows, workspace_repo_mock, costs_repo)

    rows_by_scope = {}
    for day in __persisted_days(costs_repo):
        rows_by_scope.setdefault((day.tag_name, day.tag_value), []).extend(day.rows)

    workspace_resource_groups = {row[2] for row in rows_by_scope[("tre_workspace_id", workspace_id)]}
    assert 'rg-managed-by-azure' in workspace_resource_groups
    assert 'rg-someone-else' not in workspace_resource_groups
    # and the unrelated row never reaches the TRE-wide scope either
    assert all(row[2] != 'rg-someone-else' for row in rows_by_scope[("tre_id", "guy22")])


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_ingest_export_costs_persists_query_api_row_shape(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    # Ingested rows must be indistinguishable from Query API rows so the read path
    # (summarize_untagged / report building) works unchanged.
    workspace_repo_mock.get_active_workspaces = AsyncMock(return_value=[])
    workspace_repo_mock.get_workspaces = workspace_repo_mock.get_active_workspaces
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    cost_service = CostService()
    await cost_service.ingest_export_costs(
        "guy22", GranularityEnum.daily, datetime(2022, 5, 1), datetime(2022, 5, 31),
        __exported_rows(), workspace_repo_mock, costs_repo)

    # one document per day of the ingested month
    persisted_days = [day.usage_date for day in __persisted_days(costs_repo)]
    assert persisted_days[0] == "2022-05-01"
    assert persisted_days[-1] == "2022-05-31"
    assert [10.0, 20220501, 'rg-guy22', '"tre_id":"guy22"', 'USD'] in __all_persisted_rows(costs_repo)


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_ingest_export_costs_keeps_tre_tagged_rows_from_deleted_resource_groups(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    # A deleted workspace's resource group is no longer in the tre_id resource-group list, but its
    # tre_workspace_id-tagged cost still belongs to the TRE and must be kept in the TRE-wide period
    # (otherwise export-seeded months under-report workspaces whose resource group has been removed).
    workspace_repo_mock.get_active_workspaces = AsyncMock(return_value=[])
    workspace_repo_mock.get_workspaces = workspace_repo_mock.get_active_workspaces
    get_resource_groups_by_tag_mock.return_value = {'rg-guy22': '"tre_id":"guy22"'}  # only the core RG still exists
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    rows = [
        ExportedCostRow(date=20220501, resource_group='rg-guy22', tag='"tre_core_service_id":"guy22"', cost=10.0, currency='USD'),
        # deleted workspace: its RG is not in the current tre_id RG list, but it is tre_workspace_id-tagged
        ExportedCostRow(date=20220501, resource_group='rg-guy22-ws-gone', tag='"tre_workspace_id":"deleted-ws"', cost=15.5, currency='USD'),
        # unrelated non-TRE cost must still be excluded
        ExportedCostRow(date=20220501, resource_group='rg-someone-else', tag='"owner":"other"', cost=99.0, currency='USD'),
    ]

    cost_service = CostService()
    await cost_service.ingest_export_costs(
        "guy22", GranularityEnum.daily, datetime(2022, 5, 1), datetime(2022, 5, 31),
        rows, workspace_repo_mock, costs_repo)

    persisted = __all_persisted_rows(costs_repo)
    # the deleted workspace's tagged cost is retained even though its resource group is gone
    assert [15.5, 20220501, 'rg-guy22-ws-gone', '"tre_workspace_id":"deleted-ws"', 'USD'] in persisted
    # non-TRE cost is still excluded
    assert all(row[2] != 'rg-someone-else' for row in persisted)


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_ingest_export_costs_sums_duplicate_rows(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    workspace_repo_mock.get_active_workspaces = AsyncMock(return_value=[])
    workspace_repo_mock.get_workspaces = workspace_repo_mock.get_active_workspaces
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    duplicated = [
        ExportedCostRow(date=20220501, resource_group='rg-guy22', tag='"tre_id":"guy22"', cost=1.5, currency='USD'),
        ExportedCostRow(date=20220501, resource_group='rg-guy22', tag='"tre_id":"guy22"', cost=2.5, currency='USD'),
    ]

    cost_service = CostService()
    await cost_service.ingest_export_costs(
        "guy22", GranularityEnum.daily, datetime(2022, 5, 1), datetime(2022, 5, 31),
        duplicated, workspace_repo_mock, costs_repo)

    assert __all_persisted_rows(costs_repo) == [
        [4.0, 20220501, 'rg-guy22', '"tre_id":"guy22"', 'USD']]


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_ingest_export_costs_excludes_rows_outside_the_scope(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    # Mirrors the Query API filter: only rows matching the tag or belonging to one of the
    # scope's resource groups are kept, so unrelated subscription costs are never attributed.
    workspace_repo_mock.get_active_workspaces = AsyncMock(return_value=[])
    workspace_repo_mock.get_workspaces = workspace_repo_mock.get_active_workspaces
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    rows = __exported_rows() + [
        ExportedCostRow(date=20220501, resource_group='rg-someone-else', tag='"owner":"other"',
                        cost=99.0, currency='USD')]

    cost_service = CostService()
    await cost_service.ingest_export_costs(
        "guy22", GranularityEnum.daily, datetime(2022, 5, 1), datetime(2022, 5, 31),
        rows, workspace_repo_mock, costs_repo)

    persisted_rows = __all_persisted_rows(costs_repo)
    assert all(row[2] != 'rg-someone-else' for row in persisted_rows)


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_ingest_export_costs_keeps_untagged_rows_for_resource_group_fallback(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    # An untagged row in a known TRE resource group must be kept so summarize_untagged can
    # attribute it from the resource group's tag on read.
    workspace_repo_mock.get_active_workspaces = AsyncMock(return_value=[])
    workspace_repo_mock.get_workspaces = workspace_repo_mock.get_active_workspaces
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    rows = [ExportedCostRow(date=20220501, resource_group='rg-guy22-ws-11a6', tag='',
                            cost=7.0, currency='USD')]

    cost_service = CostService()
    await cost_service.ingest_export_costs(
        "guy22", GranularityEnum.daily, datetime(2022, 5, 1), datetime(2022, 5, 31),
        rows, workspace_repo_mock, costs_repo)

    assert __all_persisted_rows(costs_repo) == [
        [7.0, 20220501, 'rg-guy22-ws-11a6', '', 'USD']]


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_ingest_export_costs_always_stores_daily_documents(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    # Cost data is only ever stored at Daily granularity, whatever granularity is requested:
    # ungranular and Monthly reports are derived from the collected days on read.
    workspace_repo_mock.get_active_workspaces = AsyncMock(return_value=[])
    workspace_repo_mock.get_workspaces = workspace_repo_mock.get_active_workspaces
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)
    costs_repo, _ = __get_costs_repo_mock(persisted=None)

    cost_service = CostService()
    await cost_service.ingest_export_costs(
        "guy22", GranularityEnum.none, datetime(2022, 5, 1), datetime(2022, 5, 31),
        __exported_rows(), workspace_repo_mock, costs_repo)

    # rows keep the Daily shape (a UsageDate column) whatever granularity was requested
    assert all(len(row) == 5 for row in __all_persisted_rows(costs_repo))


@pytest.mark.asyncio
@patch('db.repositories.workspaces.WorkspaceRepository')
@patch('services.cost_service.CostManagementClient')
@patch('services.cost_service.CostService.__wrapped__.get_resource_groups_by_tag')
async def test_ingest_export_costs_reports_are_served_from_ingested_days(
        get_resource_groups_by_tag_mock, client_mock, workspace_repo_mock):
    # End to end: days ingested from an export are read back by the report path without
    # any live Cost Management query.

    __set_workspace_repo_mock_get_active_workspaces_return_value(workspace_repo_mock)
    __set_resource_group_by_tag_return_value(get_resource_groups_by_tag_mock)

    stored = {}
    costs_repo = AsyncMock(spec=CostsRepository)

    async def __save(days):
        for day in days:
            stored[(day.tag_name, day.tag_value, day.usage_date)] = day

    async def __get(tre_id, scope, tag_name, tag_value, from_date, to_date):
        return [item for (name, value, usage_date), item in stored.items()
                if name == tag_name and value == tag_value
                and from_date <= usage_date <= to_date]

    costs_repo.build_cost_day.side_effect = CostsRepository.build_cost_day
    costs_repo.save_cost_days.side_effect = __save
    costs_repo.get_cost_days.side_effect = __get

    cost_service = CostService()
    await cost_service.ingest_export_costs(
        "guy22", GranularityEnum.daily, datetime(2022, 5, 1), datetime(2022, 5, 31),
        __exported_rows(), workspace_repo_mock, costs_repo)

    query_result = await cost_service.query_costs(
        CostService.TRE_ID_TAG, "guy22", GranularityEnum.daily,
        datetime(2022, 5, 1), datetime(2022, 5, 31),
        ['rg-guy22', 'rg-guy22-ws-11a6'], None, costs_repo)

    client_mock.return_value.query.usage.assert_not_called()
    assert [10.0, 20220501, 'rg-guy22', '"tre_id":"guy22"', 'USD'] in query_result.rows


def __exported_rows():
    return [
        ExportedCostRow(date=20220501, resource_group='rg-guy22', tag='"tre_id":"guy22"',
                        cost=10.0, currency='USD'),
        ExportedCostRow(date=20220501, resource_group='rg-guy22-ws-11a6',
                        tag='"tre_workspace_id":"19b7ce24-aa35-438c-adf6-37e6762911a6"',
                        cost=20.0, currency='USD'),
    ]
