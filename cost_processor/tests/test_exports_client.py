from datetime import date, datetime, timezone
import json
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from shared_code import exports_client


EXPORT_ENV = {
    "TRE_ID": "mytre",
    "TRE_API_URL": "https://api-test.example.com",
    "API_CLIENT_ID": "api-client-id",
    "AZURE_SUBSCRIPTION_ID": "sub-id",
    "COST_EXPORT_STORAGE_ACCOUNT": "stcostpmytre",
    "COST_EXPORT_STORAGE_ACCOUNT_ID": "/subscriptions/sub-id/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/stcostpmytre",
    "COST_EXPORT_CONTAINER": "cost-exports",
    "COST_EXPORT_LOCATION": "westeurope",
}


def _run(status="Completed", file_name="cost-exports/mytre/2026-06/part_0_0001.csv",
         submitted_time=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)):
    run = MagicMock()
    run.status = status
    run.file_name = file_name
    run.submitted_time = submitted_time
    return run


def _history(*runs):
    history = MagicMock()
    history.value = list(runs)
    return history


def _manifest_blob(name, last_modified=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)):
    blob = MagicMock()
    blob.name = name
    blob.last_modified = last_modified
    return blob


def _container_client_with_export(manifest_blobs, manifest_json, csv_by_blob):
    """Build a container client whose list_blobs/download_blob serve a partitioned export."""
    container_client = MagicMock()
    container_client.list_blobs.return_value = manifest_blobs

    def download(name, **kwargs):
        result = MagicMock()
        result.readall.return_value = manifest_json if name.endswith("manifest.json") else csv_by_blob[name]
        return result

    container_client.download_blob.side_effect = download
    return container_client


@patch.dict("os.environ", EXPORT_ENV)
def test_build_export_requests_one_month_daily_actual_cost_csv():
    export = exports_client.build_export(date(2026, 6, 1), date(2026, 6, 30))

    assert export.format == "Csv"
    assert export.partition_data is True
    assert export.definition.type == "ActualCost"
    assert export.definition.timeframe == "Custom"
    assert export.definition.data_set.granularity == "Daily"
    assert export.definition.time_period.from_property == datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert export.definition.time_period.to == datetime(2026, 6, 30, tzinfo=timezone.utc)
    assert export.delivery_info.destination.container == "cost-exports"
    assert export.delivery_info.destination.root_folder_path == "mytre/2026-06"
    assert export.delivery_info.destination.resource_id == EXPORT_ENV["COST_EXPORT_STORAGE_ACCOUNT_ID"]


@patch.dict("os.environ", EXPORT_ENV)
def test_build_export_uses_managed_identity_delivery():
    # The destination account has shared-key access disabled, so the export must be created with a
    # system-assigned managed identity (and a location) for Cost Management to deliver the CSV.
    export = exports_client.build_export(date(2026, 6, 1), date(2026, 6, 30))

    assert export.identity.type == "SystemAssigned"
    assert export.location == "westeurope"
    # A one-time export still requires a schedule; Inactive means it only runs when executed.
    assert export.schedule.status == "Inactive"


@patch.dict("os.environ", EXPORT_ENV)
def test_export_name_is_deterministic_per_month():
    assert exports_client._export_name(date(2026, 6, 1)) == "tre-mytre-costs-202606"
    assert exports_client._export_name(date(2026, 6, 1)) == exports_client._export_name(date(2026, 6, 30))


@pytest.mark.parametrize("raw,expected", [
    ("", []),
    (None, []),
    ('"tre_id": "mytre"', ['"tre_id":"mytre"']),
    ('{"tre_id": "mytre"}', ['"tre_id":"mytre"']),
    ('"tre_id": "mytre","tre_workspace_id": "ws1"', ['"tre_id":"mytre"', '"tre_workspace_id":"ws1"']),
    ("no-separator", []),
])
def test_parse_tags(raw, expected):
    assert exports_client.parse_tags(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("2026-06-01", 20260601),
    ("06/01/2026", 20260601),
    ("20260601", 20260601),
    ("2026-06-01T00:00:00", 20260601),
    ("not-a-date", None),
])
def test_parse_export_date(raw, expected):
    assert exports_client._parse_export_date(raw) == expected


def test_aggregate_export_rows_emits_one_row_per_tag_and_sums_duplicates():
    csv_text = (
        "Date,ResourceGroup,Tags,CostInBillingCurrency,BillingCurrency\n"
        '2026-06-01,rg-ws1,"""tre_id"": ""mytre"",""tre_workspace_id"": ""ws1""",10,GBP\n'
        '2026-06-01,rg-ws1,"""tre_id"": ""mytre"",""tre_workspace_id"": ""ws1""",5,GBP\n'
        "2026-06-02,rg-core,,2.5,GBP\n"
    )

    rows = exports_client.aggregate_export_rows(csv_text)

    by_key = {(r["date"], r["resource_group"], r["tag"]): r for r in rows}
    # the two rows for the same day/tag are summed rather than duplicated
    assert by_key[(20260601, "rg-ws1", '"tre_id":"mytre"')]["cost"] == 15
    assert by_key[(20260601, "rg-ws1", '"tre_workspace_id":"ws1"')]["cost"] == 15
    # an untagged resource keeps an empty tag so the API can attribute it from its resource group
    assert by_key[(20260602, "rg-core", "")]["cost"] == 2.5
    assert all(row["currency"] == "GBP" for row in rows)


def test_aggregate_export_rows_skips_rows_without_a_usable_date_or_cost():
    csv_text = (
        "Date,ResourceGroup,Tags,CostInBillingCurrency,BillingCurrency\n"
        ",rg-core,,10,GBP\n"
        "not-a-date,rg-core,,10,GBP\n"
        "2026-06-01,rg-core,,not-a-number,GBP\n"
        "2026-06-01,rg-core,,1,GBP\n"
    )

    rows = exports_client.aggregate_export_rows(csv_text)

    assert rows == [{"date": 20260601, "resource_group": "rg-core", "tag": "", "currency": "GBP", "cost": 1.0}]


def test_aggregate_export_rows_handles_alternative_column_names():
    csv_text = (
        "UsageDate,ResourceGroupName,tags,PreTaxCost,Currency\n"
        "20260601,rg-core,,3,USD\n"
    )

    rows = exports_client.aggregate_export_rows(csv_text)

    assert rows == [{"date": 20260601, "resource_group": "rg-core", "tag": "", "currency": "USD", "cost": 3.0}]


@patch.dict("os.environ", EXPORT_ENV)
def test_download_export_csv_reads_partitions_from_the_latest_manifest():
    prefix = "mytre/2026-06/tre-mytre-costs-202606"
    older = _manifest_blob(prefix + "/run1/manifest.json", datetime(2026, 6, 1, tzinfo=timezone.utc))
    newer = _manifest_blob(prefix + "/run2/manifest.json", datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc))
    manifest = json.dumps({"blobs": [
        {"blobName": prefix + "/run2/part_0_0001.csv"},
        {"blobName": prefix + "/run2/part_0_0002.csv"},
    ]})
    csv_by_blob = {
        prefix + "/run2/part_0_0001.csv": "Date,Cost\n2026-06-01,1\n",
        prefix + "/run2/part_0_0002.csv": "Date,Cost\n2026-06-02,2\n",
    }
    container_client = _container_client_with_export([older, newer], manifest, csv_by_blob)
    blob_service_client = MagicMock()
    blob_service_client.get_container_client.return_value = container_client

    text = exports_client.download_export_csv(
        blob_service_client, "mytre/2026-06", "tre-mytre-costs-202606",
        datetime(2026, 6, 15, tzinfo=timezone.utc))

    # the newer run's manifest was chosen and its partitions concatenated under one header
    container_client.download_blob.assert_any_call(newer.name)
    assert text == "Date,Cost\n2026-06-01,1\n2026-06-02,2\n"


@patch.dict("os.environ", EXPORT_ENV)
def test_download_export_csv_returns_empty_when_no_file_was_delivered():
    container_client = MagicMock()
    container_client.list_blobs.return_value = []
    blob_service_client = MagicMock()
    blob_service_client.get_container_client.return_value = container_client

    assert exports_client.download_export_csv(
        blob_service_client, "mytre/2026-06", "tre-mytre-costs-202606",
        datetime(2026, 6, 15, tzinfo=timezone.utc)) == ""


@patch.dict("os.environ", EXPORT_ENV)
@patch("shared_code.exports_client.requests.post")
@patch("shared_code.exports_client.get_access_token", return_value="a-token")
def test_ingest_rows_posts_period_and_rows_to_the_api(get_token_mock, post_mock):
    response = MagicMock()
    response.content = b"{}"
    response.json.return_value = {"collected_periods": 2}
    post_mock.return_value = response

    result = exports_client.ingest_rows(date(2026, 6, 1), date(2026, 6, 30), [{"cost": 1}])

    get_token_mock.assert_called_once_with("api-client-id")
    args, kwargs = post_mock.call_args
    assert args[0] == "https://api-test.example.com/api/internal/costs/ingest"
    assert kwargs["headers"]["Authorization"] == "Bearer a-token"
    assert kwargs["json"] == {
        "from_date": "2026-06-01", "to_date": "2026-06-30",
        "granularity": "Daily", "rows": [{"cost": 1}]}
    assert result == {"collected_periods": 2}


@patch.dict("os.environ", EXPORT_ENV)
@patch("shared_code.exports_client.requests.post")
@patch("shared_code.exports_client.get_access_token", return_value="a-token")
def test_ingest_rows_raises_on_http_error(get_token_mock, post_mock):
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("boom")
    post_mock.return_value = response

    with pytest.raises(requests.HTTPError):
        exports_client.ingest_rows(date(2026, 6, 1), date(2026, 6, 30), [])


@patch("shared_code.exports_client.time.sleep")
def test_wait_for_export_run_polls_until_completed(sleep_mock):
    client = MagicMock()
    client.exports.get_execution_history.side_effect = [
        _history(_run(status="InProgress", file_name=None)),
        _history(_run(status="Completed")),
    ]

    run = exports_client.wait_for_export_run(
        client, "/subscriptions/sub-id", "an-export", datetime(2026, 7, 1, tzinfo=timezone.utc))

    assert run.status == "Completed"
    sleep_mock.assert_called_once()


@patch("shared_code.exports_client.time.sleep")
def test_wait_for_export_run_ignores_runs_submitted_before_this_one(sleep_mock):
    stale = _run(status="Completed", submitted_time=datetime(2026, 6, 1, tzinfo=timezone.utc))
    fresh = _run(status="Completed", submitted_time=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc))
    client = MagicMock()
    client.exports.get_execution_history.side_effect = [_history(stale), _history(stale, fresh)]

    run = exports_client.wait_for_export_run(
        client, "/subscriptions/sub-id", "an-export", datetime(2026, 7, 1, tzinfo=timezone.utc))

    assert run is fresh


@patch("shared_code.exports_client.time.sleep")
def test_wait_for_export_run_raises_on_failed_status(sleep_mock):
    client = MagicMock()
    client.exports.get_execution_history.return_value = _history(
        _run(status="Failed", submitted_time=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)))

    with pytest.raises(exports_client.ExportRunFailed):
        exports_client.wait_for_export_run(
            client, "/subscriptions/sub-id", "an-export", datetime(2026, 7, 1, tzinfo=timezone.utc))


@patch("shared_code.exports_client.time.sleep")
def test_wait_for_export_run_treats_enum_status_as_running(sleep_mock):
    # SDK 5.x reports status as an ExecutionStatus enum (str() -> "ExecutionStatus.QUEUED"), which
    # must be recognised as still-running via its value rather than raising as an unknown status.
    from azure.mgmt.costmanagement.models import ExecutionStatus
    client = MagicMock()
    client.exports.get_execution_history.side_effect = [
        _history(_run(status=ExecutionStatus.QUEUED, file_name=None)),
        _history(_run(status=ExecutionStatus.COMPLETED)),
    ]

    run = exports_client.wait_for_export_run(
        client, "/subscriptions/sub-id", "an-export", datetime(2026, 7, 1, tzinfo=timezone.utc))

    assert run.status == ExecutionStatus.COMPLETED
    sleep_mock.assert_called_once()


@patch("shared_code.exports_client.time.sleep")
def test_wait_for_export_run_treats_dataready_as_success(sleep_mock):
    # The newer Exports API reports a delivered run as "DataReady" (absent from the SDK enum), which
    # must be treated as a successful terminal status rather than raising.
    client = MagicMock()
    client.exports.get_execution_history.return_value = _history(
        _run(status="DataReady", submitted_time=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)))

    run = exports_client.wait_for_export_run(
        client, "/subscriptions/sub-id", "an-export", datetime(2026, 7, 1, tzinfo=timezone.utc))

    assert exports_client._run_status(run) == "dataready"


@patch("shared_code.exports_client.time.sleep")
def test_wait_for_export_run_returns_on_empty_data_status(sleep_mock):
    # A month with no cost data ends in DataNotAvailable/NewDataNotAvailable; that is a valid empty
    # result (no manifest written), not a failure, so the run is returned for empty handling.
    client = MagicMock()
    client.exports.get_execution_history.return_value = _history(
        _run(status="DataNotAvailable", file_name=None,
             submitted_time=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)))

    run = exports_client.wait_for_export_run(
        client, "/subscriptions/sub-id", "an-export", datetime(2026, 7, 1, tzinfo=timezone.utc))

    assert exports_client._run_status(run) == "datanotavailable"


@patch("shared_code.exports_client.time.sleep")
@patch("shared_code.exports_client.time.monotonic")
def test_wait_for_export_run_times_out(monotonic_mock, sleep_mock):
    monotonic_mock.side_effect = [0, 10_000, 10_000]
    client = MagicMock()
    client.exports.get_execution_history.return_value = _history(_run(status="InProgress", file_name=None))

    with pytest.raises(exports_client.ExportRunFailed):
        exports_client.wait_for_export_run(
            client, "/subscriptions/sub-id", "an-export", datetime(2026, 7, 1, tzinfo=timezone.utc))


@patch.dict("os.environ", EXPORT_ENV)
@patch("shared_code.exports_client.ingest_rows", return_value={"collected_periods": 1})
@patch("shared_code.exports_client.wait_for_export_run")
def test_export_month_creates_runs_downloads_and_ingests(wait_mock, ingest_mock):
    wait_mock.return_value = _run()
    client = MagicMock()
    prefix = "mytre/2026-06/tre-mytre-costs-202606"
    manifest = json.dumps({"blobs": [{"blobName": prefix + "/run/000001.csv"}]})
    csv_by_blob = {prefix + "/run/000001.csv": (
        "Date,ResourceGroup,Tags,CostInBillingCurrency,BillingCurrency\n"
        "2026-06-01,rg-core,,7,GBP\n")}
    container_client = _container_client_with_export(
        [_manifest_blob(prefix + "/run/_manifest.json")], manifest, csv_by_blob)
    blob_service_client = MagicMock()
    blob_service_client.get_container_client.return_value = container_client

    result = exports_client.export_month(date(2026, 6, 1), date(2026, 6, 30), client, blob_service_client)

    client.exports.create_or_update.assert_called_once()
    scope, export_name, _ = client.exports.create_or_update.call_args[0]
    assert scope == "/subscriptions/sub-id"
    assert export_name == "tre-mytre-costs-202606"
    client.exports.execute.assert_called_once_with("/subscriptions/sub-id", "tre-mytre-costs-202606")
    assert ingest_mock.call_args[0][2] == [
        {"date": 20260601, "resource_group": "rg-core", "tag": "", "currency": "GBP", "cost": 7.0}]
    assert result["rows"] == 1


@patch.dict("os.environ", EXPORT_ENV)
@patch("shared_code.exports_client.ingest_rows", return_value={})
@patch("shared_code.exports_client.wait_for_export_run")
def test_export_month_treats_a_run_with_no_delivered_file_as_an_empty_month(wait_mock, ingest_mock):
    wait_mock.return_value = _run()
    blob_service_client = MagicMock()
    blob_service_client.get_container_client.return_value.list_blobs.return_value = []

    result = exports_client.export_month(date(2026, 6, 1), date(2026, 6, 30), MagicMock(), blob_service_client)

    assert result["rows"] == 0
    assert ingest_mock.call_args[0][2] == []


@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_finalise_previous_months_walks_back_the_configured_number_of_months(datetime_mock, export_month_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    client, blob_service_client = MagicMock(), MagicMock()

    summary = exports_client.finalise_previous_months(3, client, blob_service_client)

    assert export_month_mock.call_args_list == [
        call(date(2026, 6, 1), date(2026, 6, 30), client, blob_service_client),
        call(date(2026, 5, 1), date(2026, 5, 31), client, blob_service_client),
        call(date(2026, 4, 1), date(2026, 4, 30), client, blob_service_client),
    ]
    assert summary == {"months_finalised": 3}


@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_finalise_previous_months_crosses_the_year_boundary(datetime_mock, export_month_mock):
    datetime_mock.now.return_value = datetime(2026, 1, 10, tzinfo=timezone.utc)

    exports_client.finalise_previous_months(2, MagicMock(), MagicMock())

    assert [args[0][:2] for args in export_month_mock.call_args_list] == [
        (date(2025, 12, 1), date(2025, 12, 31)),
        (date(2025, 11, 1), date(2025, 11, 30)),
    ]


@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_finalise_previous_months_zero_look_back_does_nothing(datetime_mock, export_month_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)

    exports_client.finalise_previous_months(0, MagicMock(), MagicMock())

    export_month_mock.assert_not_called()


@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_walks_back_until_enough_empty_months(datetime_mock, export_month_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.side_effect = [
        {"rows": 5},   # June - has data
        {"rows": 3},   # May - has data
        {"rows": 0},   # April - empty
        {"rows": 0},   # March - second consecutive empty, stop
    ]

    summary = exports_client.backfill_history(client=MagicMock(), blob_service_client=MagicMock())

    assert summary == {"months_processed": 4, "months_with_data": 2}
    assert [args[0][:2] for args in export_month_mock.call_args_list] == [
        (date(2026, 6, 1), date(2026, 6, 30)),
        (date(2026, 5, 1), date(2026, 5, 31)),
        (date(2026, 4, 1), date(2026, 4, 30)),
        (date(2026, 3, 1), date(2026, 3, 31)),
    ]


@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_continues_past_a_single_empty_month(datetime_mock, export_month_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.side_effect = [{"rows": 5}, {"rows": 0}, {"rows": 4}, {"rows": 0}, {"rows": 0}]

    summary = exports_client.backfill_history(client=MagicMock(), blob_service_client=MagicMock())

    assert summary == {"months_processed": 5, "months_with_data": 2}


@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_respects_max_months(datetime_mock, export_month_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.return_value = {"rows": 5}

    summary = exports_client.backfill_history(max_months=2, client=MagicMock(), blob_service_client=MagicMock())

    assert summary == {"months_processed": 2, "months_with_data": 2}


@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_never_walks_past_cost_management_retention(datetime_mock, export_month_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.return_value = {"rows": 5}

    summary = exports_client.backfill_history(max_months=None, client=MagicMock(), blob_service_client=MagicMock())

    assert summary["months_processed"] == exports_client.BACKFILL_MAX_MONTHS_LIMIT


@patch("shared_code.exports_client.time.monotonic")
@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_stops_at_its_wall_clock_budget(datetime_mock, export_month_mock, monotonic_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.return_value = {"rows": 5}
    # start, first month within budget, second month over budget
    monotonic_mock.side_effect = [0, 10, 10_000]

    summary = exports_client.backfill_history(
        max_runtime_seconds=100, client=MagicMock(), blob_service_client=MagicMock())

    assert summary == {"months_processed": 1, "months_with_data": 1}


@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_surfaces_export_failures_instead_of_a_silent_gap(datetime_mock, export_month_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.side_effect = [{"rows": 5}, exports_client.ExportRunFailed("boom")]

    with pytest.raises(exports_client.ExportRunFailed):
        exports_client.backfill_history(client=MagicMock(), blob_service_client=MagicMock())
