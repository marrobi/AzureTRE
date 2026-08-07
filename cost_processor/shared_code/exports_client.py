"""Seed and finalise closed months from Cost Management *exports*.

Closed months are collected with one-time Cost Management exports rather than Query API
requests, following Microsoft's "Seed a historical cost dataset with the Exports API"
tutorial: one export per calendar month, executed on demand, delivering a Daily ActualCost
CSV to blob storage. Compared with the Query API this avoids the one-year-per-request limit,
returns a whole month in a single file, and is not throttled the way repeated historical
queries are.

The still-settling current month stays on the Query API (see ``api_client``) because it is
refreshed many times a day and an export run can take hours to produce a file.
"""

import codecs
import csv
import json
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

import requests
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    Export,
    ExportDataset,
    ExportDefinition,
    ExportDeliveryDestination,
    ExportDeliveryInfo,
    ExportSchedule,
    ExportTimePeriod,
    SystemAssignedServiceIdentity,
)
from azure.storage.blob import BlobServiceClient

from shared_code.api_client import (
    DEFAULT_HTTP_TIMEOUT,
    _month_bounds,
    get_access_token,
    get_credential,
    get_subscription_ids,
)

# Container the Cost Management export delivers its CSV to (created by terraform).
DEFAULT_EXPORT_CONTAINER = "cost-exports"

# How long to wait for a queued export run to produce a file before giving up on the month.
EXPORT_RUN_TIMEOUT_SECONDS = 3600
EXPORT_RUN_POLL_SECONDS = 30

# Stop the history walk only after this many *consecutive* empty months, so a single idle
# (zero-cost) month mid-history doesn't prematurely end the backfill and leave older data behind.
BACKFILL_STOP_AFTER_EMPTY_MONTHS = 2

# Overall wall-clock budget for a single backfill run. Export runs are slow, so a run is capped
# and simply resumes from where it stopped on its next schedule.
BACKFILL_MAX_RUNTIME_SECONDS = 3600 * 5

# Cost Management only retains ~13 months of data, so walking further back never returns rows.
BACKFILL_MAX_MONTHS_LIMIT = 13

# Blob holding how far back the history walk has reached. A run is capped by wall clock, so
# without this the walk would restart at the previous month every time and never reach old data.
# It sits outside the per-month export folders so the export retention policy doesn't remove it.
BACKFILL_STATE_BLOB = "_state/backfill.json"

# How long to keep looking for the manifest a completed run should have written. Blob listing is
# eventually consistent, so a manifest can lag the run status by a little.
MANIFEST_WAIT_SECONDS = 300

# Rows per ingest request. The API caps a request (so one request cannot exhaust its memory), so a
# month is posted as several contiguous day ranges rather than failing outright when it is large.
INGEST_MAX_ROWS_PER_REQUEST = 50_000

_RUNNING_STATUSES = {"queued", "inprogress", "running", "new"}
# The newer Exports API reports a delivered run as "DataReady" (not in the SDK enum); older/other
# shapes use "Completed". Both mean the CSV/manifest has been written and can be downloaded.
_SUCCESS_STATUSES = {"completed", "dataready"}
# A run for a month with no cost data ends in one of these; it is a valid empty result, not a failure.
_EMPTY_STATUSES = {"datanotavailable", "newdatanotavailable"}


class ExportRunFailed(Exception):
    """Raised when a Cost Management export run does not complete successfully."""


def _core_subscription_id() -> str:
    return os.environ["AZURE_SUBSCRIPTION_ID"]


def _export_scope(subscription_id: Optional[str] = None) -> str:
    return "/subscriptions/{}".format(subscription_id or _core_subscription_id())


def _export_location() -> str:
    """Region for the export's managed identity. Required for managed-identity-based delivery."""
    return os.environ["COST_EXPORT_LOCATION"]


def _root_folder_path(period_start: date, subscription_id: Optional[str] = None) -> str:
    """Blob folder the month's export is delivered under (also the prefix we read it back from).

    Each subscription gets its own folder: every subscription's export for a month carries the
    same (deterministic) export name, so they would otherwise deliver into the same folder and be
    read back as one another's data.
    """
    return "{}/{:%Y-%m}/{}".format(
        os.environ["TRE_ID"], period_start, subscription_id or _core_subscription_id())


def _export_name(period_start: date) -> str:
    """Deterministic per-month export name so re-runs reuse (and overwrite) the same export."""
    return "tre-{}-costs-{:%Y%m}".format(os.environ["TRE_ID"], period_start)


def get_cost_management_client() -> CostManagementClient:
    return CostManagementClient(credential=get_credential())


def get_blob_service_client() -> BlobServiceClient:
    account = os.environ["COST_EXPORT_STORAGE_ACCOUNT"]
    suffix = os.environ.get("STORAGE_ENDPOINT_SUFFIX", "core.windows.net")
    return BlobServiceClient(account_url=f"https://{account}.blob.{suffix}", credential=get_credential())


def build_export(period_start: date, period_end: date, subscription_id: Optional[str] = None) -> Export:
    """A one-time, Daily-granularity ActualCost export for a single calendar month.

    Per the tutorial, history is seeded in one-month chunks; the same shape is used to finalise
    a recently-closed month.
    """
    return Export(
        # The destination storage account has shared-key access disabled, so Cost Management must
        # deliver the CSV using the export's own system-assigned identity (granted Storage Blob Data
        # Contributor on the container when the export is created). location is required for that MI.
        identity=SystemAssignedServiceIdentity(type="SystemAssigned"),
        location=_export_location(),
        format="Csv",
        # Managed-identity delivery requires partitioned output, so a run writes one or more
        # partition CSVs plus a _manifest.json under a per-run folder instead of a single file.
        partition_data=True,
        # The API requires a schedule; an Inactive one means the export never runs on a recurrence
        # and is only produced when we execute it on demand.
        schedule=ExportSchedule(status="Inactive"),
        delivery_info=ExportDeliveryInfo(
            destination=ExportDeliveryDestination(
                container=os.environ.get("COST_EXPORT_CONTAINER", DEFAULT_EXPORT_CONTAINER),
                root_folder_path=_root_folder_path(period_start, subscription_id),
                resource_id=os.environ["COST_EXPORT_STORAGE_ACCOUNT_ID"],
            )
        ),
        definition=ExportDefinition(
            type="ActualCost",
            timeframe="Custom",
            time_period=ExportTimePeriod(
                from_property=datetime.combine(period_start, datetime.min.time()),
                to=datetime.combine(period_end, datetime.min.time()),
            ),
            data_set=ExportDataset(granularity="Daily"),
        ),
    )


def _run_status(run) -> str:
    status = getattr(run, "status", "") or ""
    # SDK 5.x returns an ExecutionStatus enum whose str() is "ExecutionStatus.QUEUED"; use its value.
    status = getattr(status, "value", status)
    return str(status).strip().lower()


def wait_for_export_run(client: CostManagementClient, scope: str, export_name: str,
                        submitted_after: datetime,
                        timeout_seconds: int = EXPORT_RUN_TIMEOUT_SECONDS,
                        poll_seconds: int = EXPORT_RUN_POLL_SECONDS):
    """Poll the export's run history until the run we queued produces a file.

    ``submitted_after`` filters out earlier runs of the same (reused) export so a stale
    successful run is never mistaken for the one just queued.
    """
    deadline = time.monotonic() + timeout_seconds
    while True:
        history = client.exports.get_execution_history(scope, export_name)
        runs = [run for run in (getattr(history, "value", None) or [])
                if run.submitted_time is None or run.submitted_time >= submitted_after]
        runs.sort(key=lambda run: run.submitted_time or submitted_after)
        latest = runs[-1] if runs else None
        if latest is not None:
            status = _run_status(latest)
            if status in _SUCCESS_STATUSES or status in _EMPTY_STATUSES:
                return latest
            if status and status not in _RUNNING_STATUSES:
                raise ExportRunFailed(f"export '{export_name}' run finished with status '{latest.status}'")
        if time.monotonic() >= deadline:
            raise ExportRunFailed(f"export '{export_name}' did not complete within {timeout_seconds}s")
        time.sleep(poll_seconds)


def _stream_blob_lines(container_client, blob_name: str) -> Iterator[str]:
    """Yield a blob's text lines without holding the whole blob in memory.

    A month's export can be hundreds of MB for a large TRE, so it is decoded incrementally
    (an incremental decoder is required because a chunk boundary can split a multi-byte char).
    """
    decoder = codecs.getincrementaldecoder("utf-8-sig")()
    remainder = ""
    for chunk in container_client.download_blob(blob_name).chunks():
        remainder += decoder.decode(chunk)
        lines = remainder.split("\n")
        remainder = lines.pop()
        for line in lines:
            yield line
    remainder += decoder.decode(b"", True)
    if remainder:
        yield remainder


def _is_manifest(blob_name: str) -> bool:
    # The manifest is named "manifest.json" by the newer Exports API (older shapes used
    # "_manifest.json"); match either so delivery is found regardless of manifest version.
    return blob_name.endswith("/manifest.json") or blob_name.endswith("/_manifest.json")


def _find_run_manifest(container_client, prefix: str, submitted_after: datetime,
                       wait_seconds: int = MANIFEST_WAIT_SECONDS,
                       poll_seconds: int = EXPORT_RUN_POLL_SECONDS):
    """The manifest written by the run submitted at ``submitted_after``, or None.

    Only manifests written at or after the run was submitted are considered. Every run of a month
    reuses the same (deterministic) export name, so falling back to an earlier run's manifest
    would silently ingest a previous run's data as if it were this run's.
    """
    deadline = time.monotonic() + wait_seconds
    while True:
        fresh = [blob for blob in container_client.list_blobs(name_starts_with=prefix)
                 if _is_manifest(blob.name)
                 and (blob.last_modified is None or blob.last_modified >= submitted_after)]
        if fresh:
            return max(fresh, key=lambda blob: blob.last_modified or submitted_after)
        if time.monotonic() >= deadline:
            return None
        time.sleep(poll_seconds)


def download_export_csv(blob_service_client: BlobServiceClient, root_folder_path: str,
                        export_name: str, submitted_after: datetime) -> Iterator[str]:
    """Yield the CSV lines the export run submitted at ``submitted_after`` wrote.

    Managed-identity delivery requires ``partitionData``, so the run history no longer carries a
    file name; instead a run writes one or more partition CSVs plus a ``manifest.json`` under a
    per-run folder. The partitions listed by that run's manifest are streamed in order under a
    single header.

    Raises ``ExportRunFailed`` if the run wrote no manifest: the caller only downloads runs that
    reported delivering data, so a missing manifest means the month is unknown, not empty, and
    must be retried rather than recorded as zero cost.
    """
    container = os.environ.get("COST_EXPORT_CONTAINER", DEFAULT_EXPORT_CONTAINER)
    container_client = blob_service_client.get_container_client(container)
    prefix = "{}/{}/".format(root_folder_path.strip("/"), export_name)

    manifest_blob = _find_run_manifest(container_client, prefix, submitted_after, MANIFEST_WAIT_SECONDS)
    if manifest_blob is None:
        raise ExportRunFailed(
            f"export '{export_name}' reported data but wrote no manifest under '{prefix}' "
            f"at or after {submitted_after.isoformat()}")

    manifest = json.loads(container_client.download_blob(manifest_blob.name).readall())
    return _stream_manifest_partitions(container_client, manifest)


def _stream_manifest_partitions(container_client, manifest: dict) -> Iterator[str]:
    for index, blob in enumerate(manifest.get("blobs", [])):
        lines = _stream_blob_lines(container_client, blob["blobName"])
        if index > 0:
            # every partition repeats the header
            next(lines, None)
        yield from lines


def _first_column(row: Dict[str, str], candidates: Iterable[str]) -> Optional[str]:
    """Case-insensitive lookup of the first present column - export column names differ by
    agreement type (EA/MCA) and export schema version."""
    lowered = {key.lower(): value for key, value in row.items() if key}
    for candidate in candidates:
        value = lowered.get(candidate.lower())
        if value not in (None, ""):
            return value
    return None


_DATE_COLUMNS = ("Date", "UsageDate", "UsageDateTime")
_RESOURCE_GROUP_COLUMNS = ("ResourceGroup", "ResourceGroupName", "resourceGroupName")
_COST_COLUMNS = ("CostInBillingCurrency", "PreTaxCost", "Cost", "costInBillingCurrency")
_CURRENCY_COLUMNS = ("BillingCurrency", "BillingCurrencyCode", "Currency", "currency")
_TAG_COLUMNS = ("Tags", "tags")


def _parse_export_date(value: str) -> Optional[int]:
    """Export date columns come in several formats; normalise to the YYYYMMDD integer the
    Query API returns so exported and queried rows are interchangeable."""
    value = value.strip()
    # drop any time component so a single set of date formats covers all schema versions
    value = value.split("T")[0].split(" ")[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return int(datetime.strptime(value, fmt).strftime("%Y%m%d"))
        except ValueError:
            continue
    return None


def parse_tags(raw: Optional[str]) -> List[str]:
    """Split an exported Tags cell into the ``"name":"value"`` pairs the Query API emits.

    Exports render tags as ``"key": "value"`` pairs (optionally wrapped in braces); the read
    path keys costs on exactly ``"name":"value"``, so each pair is normalised to that form.
    """
    if not raw:
        return []
    text = raw.strip().strip("{}").strip()
    if not text:
        return []
    tags = []
    # the cell is itself comma-separated and quoted, so re-use the CSV reader to split it
    for part in next(csv.reader([text], skipinitialspace=True), []):
        name, separator, value = part.partition(":")
        if not separator:
            continue
        tags.append('"{}":"{}"'.format(name.strip().strip('"'), value.strip().strip('"')))
    return tags


def aggregate_export_rows(csv_lines: Iterable[str]) -> List[dict]:
    """Aggregate an export CSV into the rows the API ingest endpoint expects.

    Takes an iterable of CSV lines (streamed straight from blob storage) so a large month is
    never held in memory. One row is emitted per (date, resource group, tag, currency); a
    resource carrying several TRE tags contributes a row per tag, exactly as the Query API's
    "group by Tag" does, and an untagged resource contributes a single row with an empty tag
    which the API attributes from its resource group.
    """
    aggregated: Dict[Tuple[int, str, str, str], float] = {}
    # a bare string would be iterated character by character and silently yield nothing
    if isinstance(csv_lines, str):
        csv_lines = csv_lines.splitlines()
    for row in csv.DictReader(csv_lines):
        raw_date = _first_column(row, _DATE_COLUMNS)
        usage_date = _parse_export_date(raw_date) if raw_date else None
        if usage_date is None:
            continue
        try:
            cost = float(_first_column(row, _COST_COLUMNS) or 0)
        except ValueError:
            continue
        resource_group = _first_column(row, _RESOURCE_GROUP_COLUMNS) or ""
        currency = _first_column(row, _CURRENCY_COLUMNS) or ""
        tags = parse_tags(_first_column(row, _TAG_COLUMNS)) or [""]
        for tag in tags:
            key = (usage_date, resource_group, tag, currency)
            aggregated[key] = aggregated.get(key, 0.0) + cost

    return [{"date": usage_date, "resource_group": resource_group, "tag": tag,
             "currency": currency, "cost": cost}
            for (usage_date, resource_group, tag, currency), cost in aggregated.items()]


def _day_range_chunks(period_start: date, period_end: date, rows: List[dict],
                      max_rows: int = INGEST_MAX_ROWS_PER_REQUEST):
    """Split the period into contiguous day ranges small enough to post in one request.

    Chunking by whole days (never mid-day) matters: the API replaces a day's stored costs with
    what the request carries, so a day split across two requests would keep only the second half.
    The ranges tile the whole period, so days the export returned no rows for are still covered
    and recorded as collected rather than being re-queried live forever.
    """
    rows_by_day: Dict[int, List[dict]] = {}
    for row in rows:
        rows_by_day.setdefault(row.get("date"), []).append(row)

    chunk_start = period_start
    chunk_rows: List[dict] = []
    day = period_start
    while day <= period_end:
        day_rows = rows_by_day.get(int(day.strftime("%Y%m%d")), [])
        if chunk_rows and len(chunk_rows) + len(day_rows) > max_rows:
            yield chunk_start, day - timedelta(days=1), chunk_rows
            chunk_start, chunk_rows = day, []
        chunk_rows.extend(day_rows)
        day += timedelta(days=1)
    yield chunk_start, period_end, chunk_rows


def ingest_rows(period_start: date, period_end: date, rows: List[dict],
                subscription_id: Optional[str] = None) -> dict:
    """Post the aggregated export rows to the TRE API so they are persisted as a final period.

    A large month is posted as several contiguous day ranges so it stays inside the API's
    per-request row cap instead of being rejected outright.
    """
    api_url = os.environ["TRE_API_URL"].rstrip("/")
    token = get_access_token(os.environ["API_CLIENT_ID"])
    summary: Dict[str, int] = {}

    for chunk_start, chunk_end, chunk_rows in _day_range_chunks(
            period_start, period_end, rows, INGEST_MAX_ROWS_PER_REQUEST):
        response = requests.post(
            f"{api_url}/api/internal/costs/ingest",
            json={
                "from_date": chunk_start.isoformat(),
                "to_date": chunk_end.isoformat(),
                "granularity": "Daily",
                "subscription_id": subscription_id or _core_subscription_id(),
                "rows": chunk_rows,
            },
            headers={"Authorization": "Bearer " + token},
            timeout=DEFAULT_HTTP_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json() if response.content else {}
        for key, value in result.items():
            if isinstance(value, int):
                summary[key] = summary.get(key, 0) + value
    return summary


def export_month(period_start: date, period_end: date,
                 client: Optional[CostManagementClient] = None,
                 blob_service_client: Optional[BlobServiceClient] = None,
                 subscription_ids: Optional[List[str]] = None) -> dict:
    """Create, run and ingest a one-time Cost Management export for a single calendar month.

    A TRE can span several subscriptions (workspaces may be deployed to their own), and an export
    only ever covers one, so every subscription is exported separately and ingested against its
    own scope.

    Returns ``{"rows": n}``; ``rows`` is 0 for a month with no cost data, which is how the
    history walk detects it has reached the start of the data.
    """
    client = client or get_cost_management_client()
    blob_service_client = blob_service_client or get_blob_service_client()
    if subscription_ids is None:
        subscription_ids = get_subscription_ids()

    rows = 0
    ingested = []
    for subscription_id in subscription_ids:
        try:
            rows += export_subscription_month(
                subscription_id, period_start, period_end, client, blob_service_client, ingested)
        except HttpResponseError as error:
            if error.status_code not in (401, 403, 404) or subscription_id == _core_subscription_id():
                raise
            # Cost Management Contributor has to be granted in each workspace subscription, and a
            # deleted workspace's subscription may be gone entirely. Neither must stop the rest of
            # the TRE's history being seeded.
            logging.warning("Cannot export costs for subscription %s (%s); skipping it. "
                            "Its costs will be missing from reports until access is granted.",
                            subscription_id, error.status_code)
            ingested.append({"subscription_id": subscription_id, "skipped": error.status_code})
    return {"rows": rows, "ingested": ingested}


def export_subscription_month(subscription_id: str, period_start: date, period_end: date,
                              client: CostManagementClient,
                              blob_service_client: BlobServiceClient,
                              ingested: Optional[List[dict]] = None) -> int:
    """Export and ingest one subscription's costs for a month; returns the row count."""
    scope = _export_scope(subscription_id)
    export_name = _export_name(period_start)
    root_folder_path = _root_folder_path(period_start, subscription_id)

    logging.info("Creating cost export '%s' for %s..%s in %s",
                 export_name, period_start, period_end, scope)
    client.exports.create_or_update(scope, export_name, build_export(period_start, period_end, subscription_id))

    submitted_at = datetime.now(timezone.utc)
    client.exports.execute(scope, export_name)
    run = wait_for_export_run(client, scope, export_name, submitted_at)

    if _run_status(run) in _EMPTY_STATUSES:
        # the month genuinely has no cost data, so no manifest was written; don't go looking for
        # one - the only manifest that could match is an earlier run's.
        logging.info("Cost export '%s' reported no data for %s; treating month as empty in %s.",
                     export_name, period_start, scope)
        rows: List[dict] = []
    else:
        csv_lines = download_export_csv(blob_service_client, root_folder_path, export_name, submitted_at)
        rows = aggregate_export_rows(csv_lines)

    result = ingest_rows(period_start, period_end, rows, subscription_id)
    logging.info("Ingested %s aggregated row(s) for %s..%s in %s: %s",
                 len(rows), period_start, period_end, scope, result)
    if ingested is not None:
        ingested.append({"subscription_id": subscription_id, "rows": len(rows), "ingested": result})
    return len(rows)


def _months_back(count: Optional[int], start_month: Optional[date] = None) -> Iterator[Tuple[date, date]]:
    """Yield (first_day, last_day) for each month, newest first.

    Starts at ``start_month`` when given, otherwise at the previous (most recently closed) month.
    """
    if start_month is None:
        today = datetime.now(timezone.utc).date()
        month_end = _month_bounds(today)[0] - timedelta(days=1)
    else:
        month_end = _month_bounds(start_month)[1] - timedelta(days=1)
    produced = 0
    while count is None or produced < count:
        month_first, next_first = _month_bounds(month_end)
        yield month_first, next_first - timedelta(days=1)
        produced += 1
        month_end = month_first - timedelta(days=1)


def _previous_month(reference: date) -> date:
    return _month_bounds(reference)[0] - timedelta(days=1)


def _state_container_client(blob_service_client: BlobServiceClient):
    container = os.environ.get("COST_EXPORT_CONTAINER", DEFAULT_EXPORT_CONTAINER)
    return blob_service_client.get_container_client(container)


def load_backfill_state(blob_service_client: BlobServiceClient) -> dict:
    """How far back the history walk has already reached; empty when it has never run."""
    try:
        content = _state_container_client(blob_service_client).download_blob(BACKFILL_STATE_BLOB).readall()
        state = json.loads(content)
        return state if isinstance(state, dict) else {}
    except ResourceNotFoundError:
        logging.info("No cost backfill state yet; starting from the previous month.")
        return {}
    except Exception:
        # Without the cursor the walk restarts at the previous month and re-exports months it
        # already has, so a cursor we cannot read is worth noticing rather than absorbing.
        logging.warning("Could not read the cost backfill state; starting from the previous month "
                        "and re-exporting months already collected.", exc_info=True)
        return {}


def save_backfill_state(blob_service_client: BlobServiceClient, state: dict) -> None:
    try:
        _state_container_client(blob_service_client).upload_blob(
            BACKFILL_STATE_BLOB, json.dumps(state), overwrite=True)
    except Exception:
        # losing the cursor only costs a repeated export next run, so don't fail the backfill
        logging.warning("Could not persist cost backfill state.", exc_info=True)


def finalise_previous_months(look_back_months: int = 1,
                             client: Optional[CostManagementClient] = None,
                             blob_service_client: Optional[BlobServiceClient] = None) -> dict:
    """Re-export recently-closed months so they are finalised in the collection.

    Azure keeps re-rating a month for a while after it closes, so each recently-closed month is
    re-exported and the ingested period overwrites the previous one.
    """
    client = client or get_cost_management_client()
    blob_service_client = blob_service_client or get_blob_service_client()
    subscription_ids = get_subscription_ids()
    months = 0
    for period_start, period_end in _months_back(max(look_back_months, 0)):
        export_month(period_start, period_end, client, blob_service_client, subscription_ids)
        months += 1
    return {"months_finalised": months}


def _subscription_backfill_states(state: dict, subscription_ids: List[str]) -> Dict[str, dict]:
    """Return backfill progress keyed by subscription, upgrading the old single cursor in memory."""
    states = state.get("subscriptions")
    if not isinstance(states, dict):
        states = {}
        if any(key in state for key in ("oldest_processed", "consecutive_empty", "complete")):
            configured_core = os.environ.get("AZURE_SUBSCRIPTION_ID")
            legacy_subscription = (configured_core if configured_core in subscription_ids
                                   else subscription_ids[0] if subscription_ids else None)
            if legacy_subscription:
                states[legacy_subscription] = {
                    key: state[key] for key in ("oldest_processed", "consecutive_empty", "complete")
                    if key in state}

    for subscription_id in subscription_ids:
        states.setdefault(subscription_id, {"consecutive_empty": 0, "complete": False})
    return states


def _backfill_state_payload(states: Dict[str, dict], subscription_ids: List[str]) -> dict:
    """Serialize per-subscription progress, retaining old top-level fields for one subscription."""
    payload = {"subscriptions": states}
    if len(subscription_ids) == 1:
        payload.update(states[subscription_ids[0]])
    return payload


def _subscription_export_was_skipped(result: dict, subscription_id: str) -> bool:
    return any(item.get("subscription_id") == subscription_id and "skipped" in item
               for item in result.get("ingested", []))


def backfill_history(max_months: Optional[int] = None,
                     stop_after_empty_months: int = BACKFILL_STOP_AFTER_EMPTY_MONTHS,
                     max_runtime_seconds: Optional[int] = BACKFILL_MAX_RUNTIME_SECONDS,
                     client: Optional[CostManagementClient] = None,
                     blob_service_client: Optional[BlobServiceClient] = None) -> dict:
    """Seed cost history by exporting one month at a time, walking backwards.

    Follows the tutorial's "execute the requests in one-month chunks" guidance. The walk stops
    after ``stop_after_empty_months`` *consecutive* empty months (so a single idle month does not
    end it early), once ``max_months`` months have been processed, once ``max_runtime_seconds``
    of wall clock has elapsed, or once it reaches Cost Management's ~13 month retention window.

    Export runs are slow, so a run rarely covers the whole history. How far back it reached is
    recorded, and the next scheduled run continues from there instead of re-exporting the months
    it already has - otherwise a run capped by wall clock would keep redoing the newest months and
    never reach the oldest ones.
    """
    client = client or get_cost_management_client()
    blob_service_client = blob_service_client or get_blob_service_client()

    state = load_backfill_state(blob_service_client)
    limit = min(max_months, BACKFILL_MAX_MONTHS_LIMIT) if max_months else BACKFILL_MAX_MONTHS_LIMIT
    subscription_ids = get_subscription_ids()
    subscription_states = _subscription_backfill_states(state, subscription_ids)
    pending_subscriptions = [subscription_id for subscription_id in subscription_ids
                             if not subscription_states[subscription_id].get("complete")]
    if not pending_subscriptions:
        logging.info("Cost history backfill already reached the start of the data; nothing to do.")
        return {"months_processed": 0, "months_with_data": 0, "complete": True}

    # never walk past Cost Management's retention window, however far the cursor has got
    earliest_allowed = _month_bounds(datetime.now(timezone.utc).date())[0]
    for _ in range(BACKFILL_MAX_MONTHS_LIMIT):
        earliest_allowed = _month_bounds(earliest_allowed - timedelta(days=1))[0]

    months_processed = 0
    months_with_data = 0
    export_attempts = 0
    started_at = time.monotonic()
    stopped_for_runtime = False

    # Round-robin prevents a slow core-subscription history from starving workspace subscriptions.
    while pending_subscriptions and export_attempts < limit and not stopped_for_runtime:
        for subscription_id in list(pending_subscriptions):
            if export_attempts >= limit:
                break
            subscription_state = subscription_states[subscription_id]
            start_month = None
            oldest_processed = subscription_state.get("oldest_processed")
            if oldest_processed:
                try:
                    start_month = _previous_month(date.fromisoformat(oldest_processed + "-01"))
                except ValueError:
                    logging.warning("Ignoring unparsable cost backfill cursor '%s' for %s.",
                                    oldest_processed, subscription_id)
            period_start, period_end = next(_months_back(1, start_month))

            if period_start < earliest_allowed:
                logging.info("Backfill reached Cost Management's retention window at %s in %s; "
                             "stopping.", period_start, subscription_id)
                subscription_state["complete"] = True
                pending_subscriptions.remove(subscription_id)
                save_backfill_state(
                    blob_service_client, _backfill_state_payload(subscription_states, subscription_ids))
                continue
            if max_runtime_seconds and (time.monotonic() - started_at) >= max_runtime_seconds:
                logging.info("Backfill reached its wall-clock budget of %ss after %s month(s); "
                             "remaining subscriptions will resume on the next scheduled run.",
                             max_runtime_seconds, months_processed)
                stopped_for_runtime = True
                break

            export_attempts += 1
            result = export_month(
                period_start, period_end, client, blob_service_client, [subscription_id])
            if _subscription_export_was_skipped(result, subscription_id):
                # Do not retry repeatedly in this invocation, but leave its durable cursor unchanged.
                pending_subscriptions.remove(subscription_id)
                continue

            months_processed += 1
            subscription_state["oldest_processed"] = "{:%Y-%m}".format(period_start)
            subscription_state["complete"] = False
            if result["rows"] == 0:
                consecutive_empty = int(subscription_state.get("consecutive_empty", 0)) + 1
                subscription_state["consecutive_empty"] = consecutive_empty
                if consecutive_empty >= stop_after_empty_months:
                    logging.info("Backfill reached %s consecutive month(s) with no cost data "
                                 "(through %s) in %s; stopping.",
                                 consecutive_empty, period_start, subscription_id)
                    subscription_state["complete"] = True
                    pending_subscriptions.remove(subscription_id)
            else:
                subscription_state["consecutive_empty"] = 0
                months_with_data += 1
            save_backfill_state(
                blob_service_client, _backfill_state_payload(subscription_states, subscription_ids))

    complete = all(subscription_states[subscription_id].get("complete")
                   for subscription_id in subscription_ids)

    logging.info("Cost history backfill finished: %s month(s) processed, %s with data.",
                 months_processed, months_with_data)
    return {"months_processed": months_processed, "months_with_data": months_with_data,
            "complete": complete}
