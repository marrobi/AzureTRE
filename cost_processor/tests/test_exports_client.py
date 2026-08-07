from datetime import date, datetime, timedelta, timezone
import json
from unittest.mock import ANY, MagicMock, call, patch

import pytest
import requests
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

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
    """Build a container client whose list_blobs/download_blob serve a partitioned export.

    Partition CSVs are served as byte chunks, split mid-line and mid-multi-byte-character, to
    exercise the incremental streaming the downloader relies on.
    """
    container_client = MagicMock()
    container_client.list_blobs.return_value = manifest_blobs

    def download(name, **kwargs):
        result = MagicMock()
        if name.endswith("manifest.json"):
            result.readall.return_value = manifest_json
        else:
            data = csv_by_blob[name].encode("utf-8")
            result.chunks.return_value = [data[i:i + 7] for i in range(0, len(data), 7)]
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
    # the folder is per subscription: every subscription's export for a month shares one name
    assert export.delivery_info.destination.root_folder_path == "mytre/2026-06/sub-id"
    assert export.delivery_info.destination.resource_id == EXPORT_ENV["COST_EXPORT_STORAGE_ACCOUNT_ID"]


@patch.dict("os.environ", EXPORT_ENV)
def test_build_export_delivers_each_subscription_to_its_own_folder():
    core = exports_client.build_export(date(2026, 6, 1), date(2026, 6, 30))
    workspace = exports_client.build_export(date(2026, 6, 1), date(2026, 6, 30), "sub-ws")

    assert core.delivery_info.destination.root_folder_path == "mytre/2026-06/sub-id"
    assert workspace.delivery_info.destination.root_folder_path == "mytre/2026-06/sub-ws"


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
    prefix = "mytre/2026-06/sub-id/tre-mytre-costs-202606"
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

    lines = list(exports_client.download_export_csv(
        blob_service_client, "mytre/2026-06/sub-id", "tre-mytre-costs-202606",
        datetime(2026, 6, 15, tzinfo=timezone.utc)))

    # the newer run's manifest was chosen and its partitions streamed under one header
    container_client.download_blob.assert_any_call(newer.name)
    assert lines == ["Date,Cost", "2026-06-01,1", "2026-06-02,2"]


@patch.dict("os.environ", EXPORT_ENV)
@patch("shared_code.exports_client.MANIFEST_WAIT_SECONDS", 0)
@patch("shared_code.exports_client.time.sleep")
def test_download_export_csv_never_falls_back_to_an_earlier_runs_manifest(sleep_mock):
    # Every run of a month reuses the same export name, so an earlier run's manifest sits in the
    # same folder. Reading it would ingest stale costs as if they were this run's.
    prefix = "mytre/2026-06/sub-id/tre-mytre-costs-202606"
    stale = _manifest_blob(prefix + "/run1/manifest.json", datetime(2026, 6, 1, tzinfo=timezone.utc))
    manifest = json.dumps({"blobs": [{"blobName": prefix + "/run1/part_0_0001.csv"}]})
    container_client = _container_client_with_export(
        [stale], manifest, {prefix + "/run1/part_0_0001.csv": "Date,Cost\n2026-06-01,999\n"})
    blob_service_client = MagicMock()
    blob_service_client.get_container_client.return_value = container_client

    with pytest.raises(exports_client.ExportRunFailed):
        list(exports_client.download_export_csv(
            blob_service_client, "mytre/2026-06/sub-id", "tre-mytre-costs-202606",
            datetime(2026, 7, 1, tzinfo=timezone.utc)))


@patch.dict("os.environ", EXPORT_ENV)
@patch("shared_code.exports_client.MANIFEST_WAIT_SECONDS", 0)
@patch("shared_code.exports_client.time.sleep")
def test_download_export_csv_fails_when_a_delivering_run_wrote_no_manifest(sleep_mock):
    container_client = MagicMock()
    container_client.list_blobs.return_value = []
    blob_service_client = MagicMock()
    blob_service_client.get_container_client.return_value = container_client

    with pytest.raises(exports_client.ExportRunFailed):
        list(exports_client.download_export_csv(
            blob_service_client, "mytre/2026-06/sub-id", "tre-mytre-costs-202606",
            datetime(2026, 6, 15, tzinfo=timezone.utc)))


@patch.dict("os.environ", EXPORT_ENV)
@patch("shared_code.exports_client.requests.post")
@patch("shared_code.exports_client.get_access_token", return_value="a-token")
def test_ingest_rows_posts_period_and_rows_to_the_api(get_token_mock, post_mock):
    response = MagicMock()
    response.content = b"{}"
    response.json.return_value = {"collected_periods": 2}
    post_mock.return_value = response

    row = {"date": 20260601, "resource_group": "rg", "tag": "", "currency": "GBP", "cost": 1}
    result = exports_client.ingest_rows(date(2026, 6, 1), date(2026, 6, 30), [row])

    get_token_mock.assert_called_once_with("api-client-id")
    args, kwargs = post_mock.call_args
    assert args[0] == "https://api-test.example.com/api/internal/costs/ingest"
    assert kwargs["headers"]["Authorization"] == "Bearer a-token"
    assert kwargs["json"] == {
        "from_date": "2026-06-01", "to_date": "2026-06-30",
        "granularity": "Daily", "subscription_id": "sub-id", "rows": [row]}
    assert result == {"collected_periods": 2}


@patch.dict("os.environ", EXPORT_ENV)
@patch("shared_code.exports_client.requests.post")
@patch("shared_code.exports_client.get_access_token", return_value="a-token")
def test_ingest_rows_attributes_the_rows_to_the_exported_subscription(get_token_mock, post_mock):
    response = MagicMock()
    response.content = b"{}"
    response.json.return_value = {}
    post_mock.return_value = response

    exports_client.ingest_rows(date(2026, 6, 1), date(2026, 6, 30), [], "sub-ws")

    assert post_mock.call_args.kwargs["json"]["subscription_id"] == "sub-ws"


@patch.dict("os.environ", EXPORT_ENV)
@patch("shared_code.exports_client.INGEST_MAX_ROWS_PER_REQUEST", 3)
@patch("shared_code.exports_client.requests.post")
@patch("shared_code.exports_client.get_access_token", return_value="a-token")
def test_ingest_rows_splits_a_large_month_into_whole_day_ranges(get_token_mock, post_mock):
    # The API caps rows per request, so a big month is posted in several requests. Splitting on
    # day boundaries matters: the API replaces a day's costs with what the request carries, so a
    # day spread over two requests would keep only the second half.
    response = MagicMock()
    response.content = b"{}"
    response.json.return_value = {"collected_periods": 1, "total_rows": 3}
    post_mock.return_value = response

    rows = [{"date": 20260600 + day, "resource_group": f"rg{index}", "tag": "",
             "currency": "GBP", "cost": 1}
            for day in range(1, 4) for index in range(3)]

    result = exports_client.ingest_rows(date(2026, 6, 1), date(2026, 6, 3), rows)

    periods = [(call.kwargs["json"]["from_date"], call.kwargs["json"]["to_date"])
               for call in post_mock.call_args_list]
    posted = [row for call in post_mock.call_args_list for row in call.kwargs["json"]["rows"]]
    # the ranges tile the period without overlapping, and no row is lost or duplicated
    assert periods == [("2026-06-01", "2026-06-01"), ("2026-06-02", "2026-06-02"),
                       ("2026-06-03", "2026-06-03")]
    assert posted == rows
    # per-request results are summed so the caller still sees one total
    assert result == {"collected_periods": 3, "total_rows": 9}


@patch.dict("os.environ", EXPORT_ENV)
@patch("shared_code.exports_client.requests.post")
@patch("shared_code.exports_client.get_access_token", return_value="a-token")
def test_ingest_rows_covers_days_with_no_cost_rows(get_token_mock, post_mock):
    # Days the export returned nothing for must still be ingested, otherwise they are treated as
    # never collected and re-queried live forever.
    response = MagicMock()
    response.content = b"{}"
    response.json.return_value = {}
    post_mock.return_value = response

    exports_client.ingest_rows(date(2026, 6, 1), date(2026, 6, 30), [])

    assert post_mock.call_count == 1
    assert post_mock.call_args.kwargs["json"]["from_date"] == "2026-06-01"
    assert post_mock.call_args.kwargs["json"]["to_date"] == "2026-06-30"


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
@patch("shared_code.exports_client.MANIFEST_WAIT_SECONDS", 0)
@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id"])
@patch("shared_code.exports_client.ingest_rows", return_value={"collected_periods": 1})
@patch("shared_code.exports_client.wait_for_export_run")
def test_export_month_creates_runs_downloads_and_ingests(wait_mock, ingest_mock, subscriptions_mock):
    wait_mock.return_value = _run()
    client = MagicMock()
    prefix = "mytre/2026-06/sub-id/tre-mytre-costs-202606"
    manifest = json.dumps({"blobs": [{"blobName": prefix + "/run/000001.csv"}]})
    csv_by_blob = {prefix + "/run/000001.csv": (
        "Date,ResourceGroup,Tags,CostInBillingCurrency,BillingCurrency\n"
        "2026-06-01,rg-core,,7,GBP\n")}
    container_client = _container_client_with_export(
        # written by the run this test performs, so it is newer than the run's submission time
        [_manifest_blob(prefix + "/run/_manifest.json", datetime.now(timezone.utc) + timedelta(minutes=5))],
        manifest, csv_by_blob)
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
def test_export_month_treats_a_no_data_run_as_an_empty_month_without_reading_blobs(wait_mock, ingest_mock):
    # A month with no cost data writes no manifest, so there is nothing to look for - and the only
    # manifest that could match would be an earlier run's.
    wait_mock.return_value = _run(status="DataNotAvailable", file_name=None)
    blob_service_client = MagicMock()

    result = exports_client.export_month(
        date(2026, 6, 1), date(2026, 6, 30), MagicMock(), blob_service_client, ["sub-id"])

    assert result["rows"] == 0
    assert ingest_mock.call_args[0][2] == []
    blob_service_client.get_container_client.return_value.list_blobs.assert_not_called()


@patch.dict("os.environ", EXPORT_ENV)
@patch("shared_code.exports_client.ingest_rows", return_value={})
@patch("shared_code.exports_client.wait_for_export_run")
def test_export_month_exports_every_subscription_separately(wait_mock, ingest_mock):
    # A TRE can span subscriptions and an export only covers one, so each is exported and ingested
    # against its own scope.
    wait_mock.return_value = _run(status="DataNotAvailable", file_name=None)
    client = MagicMock()

    exports_client.export_month(date(2026, 6, 1), date(2026, 6, 30), client, MagicMock(),
                                ["sub-id", "sub-ws"])

    assert [args[0][0] for args in client.exports.execute.call_args_list] == [
        "/subscriptions/sub-id", "/subscriptions/sub-ws"]
    assert [args[0][3] for args in ingest_mock.call_args_list] == ["sub-id", "sub-ws"]


@patch.dict("os.environ", EXPORT_ENV)
@patch("shared_code.exports_client.ingest_rows", return_value={})
@patch("shared_code.exports_client.wait_for_export_run")
@pytest.mark.parametrize("status_code", [403, 404])
def test_export_month_skips_a_workspace_subscription_it_cannot_read(wait_mock, ingest_mock, status_code):
    # Cost Management Contributor has to be granted in each workspace subscription, and a deleted
    # workspace's subscription may be gone entirely - neither must stop the rest being collected.
    wait_mock.return_value = _run(status="DataNotAvailable", file_name=None)
    client = MagicMock()
    client.exports.create_or_update.side_effect = [
        MagicMock(), HttpResponseError(response=MagicMock(status_code=status_code))]

    result = exports_client.export_month(date(2026, 6, 1), date(2026, 6, 30), client, MagicMock(),
                                         ["sub-id", "sub-ws"])

    assert {"subscription_id": "sub-ws", "skipped": status_code} in result["ingested"]


@patch.dict("os.environ", EXPORT_ENV)
@patch("shared_code.exports_client.ingest_rows", return_value={})
@patch("shared_code.exports_client.wait_for_export_run")
def test_export_month_surfaces_unexpected_failures_for_a_workspace_subscription(wait_mock, ingest_mock):
    # only "we can't see this subscription" is skippable; a real fault must not be absorbed
    wait_mock.return_value = _run(status="DataNotAvailable", file_name=None)
    client = MagicMock()
    client.exports.create_or_update.side_effect = [
        MagicMock(), HttpResponseError(response=MagicMock(status_code=500))]

    with pytest.raises(HttpResponseError):
        exports_client.export_month(date(2026, 6, 1), date(2026, 6, 30), client, MagicMock(),
                                    ["sub-id", "sub-ws"])


@patch.dict("os.environ", EXPORT_ENV)
@patch("shared_code.exports_client.wait_for_export_run")
def test_export_month_still_fails_when_the_core_subscription_is_forbidden(wait_mock):
    client = MagicMock()
    client.exports.create_or_update.side_effect = HttpResponseError(response=MagicMock(status_code=403))

    with pytest.raises(HttpResponseError):
        exports_client.export_month(date(2026, 6, 1), date(2026, 6, 30), client, MagicMock(), ["sub-id"])


@patch.dict("os.environ", EXPORT_ENV)
def test_load_backfill_state_returns_empty_on_the_first_ever_run():
    blob_service_client = MagicMock()
    blob_service_client.get_container_client.return_value.download_blob.side_effect = \
        ResourceNotFoundError("no such blob")

    assert exports_client.load_backfill_state(blob_service_client) == {}


@patch.dict("os.environ", EXPORT_ENV)
def test_load_backfill_state_warns_when_the_cursor_cannot_be_read():
    # falling back to the previous month silently would re-export months already collected
    blob_service_client = MagicMock()
    blob_service_client.get_container_client.return_value.download_blob.side_effect = \
        HttpResponseError(response=MagicMock(status_code=403))

    with patch("shared_code.exports_client.logging.warning") as warning_mock:
        assert exports_client.load_backfill_state(blob_service_client) == {}

    warning_mock.assert_called_once()


@patch.dict("os.environ", EXPORT_ENV)
def test_backfill_state_round_trips():
    blob_service_client = MagicMock()
    container_client = blob_service_client.get_container_client.return_value

    exports_client.save_backfill_state(blob_service_client, {"oldest_processed": "2026-03"})

    name, payload = container_client.upload_blob.call_args[0]
    # kept outside the per-month export folders so the export retention policy can't remove it
    assert name == exports_client.BACKFILL_STATE_BLOB
    assert not name.startswith("mytre/")
    assert json.loads(payload) == {"oldest_processed": "2026-03"}


@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id"])
@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_finalise_previous_months_walks_back_the_configured_number_of_months(
        datetime_mock, export_month_mock, subscriptions_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    client, blob_service_client = MagicMock(), MagicMock()

    summary = exports_client.finalise_previous_months(3, client, blob_service_client)

    assert export_month_mock.call_args_list == [
        call(date(2026, 6, 1), date(2026, 6, 30), client, blob_service_client, ["sub-id"]),
        call(date(2026, 5, 1), date(2026, 5, 31), client, blob_service_client, ["sub-id"]),
        call(date(2026, 4, 1), date(2026, 4, 30), client, blob_service_client, ["sub-id"]),
    ]
    assert summary == {"months_finalised": 3}


@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id"])
@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_finalise_previous_months_crosses_the_year_boundary(datetime_mock, export_month_mock, subscriptions_mock):
    datetime_mock.now.return_value = datetime(2026, 1, 10, tzinfo=timezone.utc)

    exports_client.finalise_previous_months(2, MagicMock(), MagicMock())

    assert [args[0][:2] for args in export_month_mock.call_args_list] == [
        (date(2025, 12, 1), date(2025, 12, 31)),
        (date(2025, 11, 1), date(2025, 11, 30)),
    ]


@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id"])
@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_finalise_previous_months_zero_look_back_does_nothing(datetime_mock, export_month_mock, subscriptions_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)

    exports_client.finalise_previous_months(0, MagicMock(), MagicMock())

    export_month_mock.assert_not_called()


@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id"])
@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_walks_back_until_enough_empty_months(
        datetime_mock, export_month_mock, subscriptions_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.side_effect = [
        {"rows": 5},   # June - has data
        {"rows": 3},   # May - has data
        {"rows": 0},   # April - empty
        {"rows": 0},   # March - second consecutive empty, stop
    ]

    summary = exports_client.backfill_history(client=MagicMock(), blob_service_client=MagicMock())

    assert summary == {"months_processed": 4, "months_with_data": 2, "complete": True}
    assert [args[0][:2] for args in export_month_mock.call_args_list] == [
        (date(2026, 6, 1), date(2026, 6, 30)),
        (date(2026, 5, 1), date(2026, 5, 31)),
        (date(2026, 4, 1), date(2026, 4, 30)),
        (date(2026, 3, 1), date(2026, 3, 31)),
    ]


@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id"])
@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_continues_past_a_single_empty_month(
        datetime_mock, export_month_mock, subscriptions_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.side_effect = [{"rows": 5}, {"rows": 0}, {"rows": 4}, {"rows": 0}, {"rows": 0}]

    summary = exports_client.backfill_history(client=MagicMock(), blob_service_client=MagicMock())

    assert summary == {"months_processed": 5, "months_with_data": 2, "complete": True}


@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id"])
@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_respects_max_months(datetime_mock, export_month_mock, subscriptions_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.return_value = {"rows": 5}

    summary = exports_client.backfill_history(max_months=2, client=MagicMock(), blob_service_client=MagicMock())

    assert summary == {"months_processed": 2, "months_with_data": 2, "complete": False}


@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id"])
@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_never_walks_past_cost_management_retention(
        datetime_mock, export_month_mock, subscriptions_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.return_value = {"rows": 5}

    summary = exports_client.backfill_history(max_months=None, client=MagicMock(), blob_service_client=MagicMock())

    assert summary["months_processed"] == exports_client.BACKFILL_MAX_MONTHS_LIMIT


@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id"])
@patch("shared_code.exports_client.load_backfill_state",
       return_value={"oldest_processed": "2025-07", "consecutive_empty": 0})
@patch("shared_code.exports_client.save_backfill_state")
@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_stops_at_retention_even_when_resuming(
        datetime_mock, export_month_mock, save_mock, load_mock, subscriptions_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.return_value = {"rows": 5}

    summary = exports_client.backfill_history(client=MagicMock(), blob_service_client=MagicMock())

    # 2025-06 is the oldest month still inside the ~13 month window, and nothing older is attempted
    assert [args[0][0] for args in export_month_mock.call_args_list] == [date(2025, 6, 1)]
    assert summary["complete"] is True


@patch("shared_code.exports_client.time.monotonic")
@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id"])
@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_stops_at_its_wall_clock_budget(
        datetime_mock, export_month_mock, subscriptions_mock, monotonic_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.return_value = {"rows": 5}
    # start, first month within budget, second month over budget
    monotonic_mock.side_effect = [0, 10, 10_000]

    summary = exports_client.backfill_history(
        max_runtime_seconds=100, client=MagicMock(), blob_service_client=MagicMock())

    assert summary == {"months_processed": 1, "months_with_data": 1, "complete": False}


@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id"])
@patch("shared_code.exports_client.load_backfill_state",
       return_value={"oldest_processed": "2026-04", "consecutive_empty": 0})
@patch("shared_code.exports_client.save_backfill_state")
@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_resumes_below_the_month_the_last_run_reached(
        datetime_mock, export_month_mock, save_mock, load_mock, subscriptions_mock):
    # A run is capped by wall clock, so without resuming it would re-export the newest months
    # every night and never reach the oldest ones.
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.return_value = {"rows": 5}

    exports_client.backfill_history(max_months=2, client=MagicMock(), blob_service_client=MagicMock())

    assert [args[0][:2] for args in export_month_mock.call_args_list] == [
        (date(2026, 3, 1), date(2026, 3, 31)),
        (date(2026, 2, 1), date(2026, 2, 28)),
    ]


@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id"])
@patch("shared_code.exports_client.load_backfill_state", return_value={"complete": True})
@patch("shared_code.exports_client.export_month")
def test_backfill_history_does_nothing_once_it_has_reached_the_start_of_the_data(
        export_month_mock, load_mock, subscriptions_mock):
    summary = exports_client.backfill_history(client=MagicMock(), blob_service_client=MagicMock())

    export_month_mock.assert_not_called()
    assert summary == {"months_processed": 0, "months_with_data": 0, "complete": True}


@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id"])
@patch("shared_code.exports_client.load_backfill_state", return_value={})
@patch("shared_code.exports_client.save_backfill_state")
@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_records_progress_after_every_month(
        datetime_mock, export_month_mock, save_mock, load_mock, subscriptions_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.return_value = {"rows": 5}

    exports_client.backfill_history(max_months=2, client=MagicMock(), blob_service_client=MagicMock())

    assert [args[0][1]["oldest_processed"] for args in save_mock.call_args_list] == ["2026-06", "2026-05"]


@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id"])
@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_surfaces_export_failures_instead_of_a_silent_gap(
        datetime_mock, export_month_mock, subscriptions_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.side_effect = [{"rows": 5}, exports_client.ExportRunFailed("boom")]

    with pytest.raises(exports_client.ExportRunFailed):
        exports_client.backfill_history(client=MagicMock(), blob_service_client=MagicMock())


@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id", "sub-ws"])
@patch("shared_code.exports_client.load_backfill_state", return_value={})
@patch("shared_code.exports_client.save_backfill_state")
@patch("shared_code.exports_client.export_month")
@patch("shared_code.exports_client.datetime")
def test_backfill_history_does_not_advance_a_skipped_subscription(
        datetime_mock, export_month_mock, save_mock, load_mock, subscriptions_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    export_month_mock.side_effect = [
        {"rows": 5, "ingested": [{"subscription_id": "sub-id", "rows": 5}]},
        {"rows": 0, "ingested": [{"subscription_id": "sub-ws", "skipped": 403}]},
    ]

    summary = exports_client.backfill_history(
        max_months=2, client=MagicMock(), blob_service_client=MagicMock())

    saved_state = save_mock.call_args_list[-1].args[1]
    assert saved_state["subscriptions"]["sub-id"]["oldest_processed"] == "2026-06"
    assert saved_state["subscriptions"]["sub-ws"] == {
        "consecutive_empty": 0, "complete": False}
    assert summary["complete"] is False


@patch("shared_code.exports_client.get_subscription_ids", return_value=["sub-id", "sub-new"])
@patch("shared_code.exports_client.load_backfill_state", return_value={
    "subscriptions": {
        "sub-id": {"oldest_processed": "2025-06", "consecutive_empty": 2, "complete": True}
    }
})
@patch("shared_code.exports_client.save_backfill_state")
@patch("shared_code.exports_client.export_month", return_value={"rows": 5, "ingested": []})
@patch("shared_code.exports_client.datetime")
def test_backfill_history_starts_a_subscription_discovered_after_core_completed(
        datetime_mock, export_month_mock, save_mock, load_mock, subscriptions_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)

    summary = exports_client.backfill_history(
        max_months=1, client=MagicMock(), blob_service_client=MagicMock())

    export_month_mock.assert_called_once_with(
        date(2026, 6, 1), date(2026, 6, 30),
        ANY, ANY, ["sub-new"])
    assert summary == {"months_processed": 1, "months_with_data": 1, "complete": False}
