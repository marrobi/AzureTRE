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

import csv
import io
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

import requests
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    Export,
    ExportDataset,
    ExportDefinition,
    ExportDeliveryDestination,
    ExportDeliveryInfo,
    ExportTimePeriod,
)
from azure.storage.blob import BlobServiceClient

from shared_code.api_client import DEFAULT_HTTP_TIMEOUT, _month_bounds, get_access_token, get_credential

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

_RUNNING_STATUSES = {"queued", "inprogress", "inprogress ", "running", "new"}
_SUCCESS_STATUSES = {"completed"}


class ExportRunFailed(Exception):
    """Raised when a Cost Management export run does not complete successfully."""


def _export_scope() -> str:
    return "/subscriptions/{}".format(os.environ["AZURE_SUBSCRIPTION_ID"])


def _export_name(period_start: date) -> str:
    """Deterministic per-month export name so re-runs reuse (and overwrite) the same export."""
    return "tre-{}-costs-{:%Y%m}".format(os.environ["TRE_ID"], period_start)


def get_cost_management_client() -> CostManagementClient:
    return CostManagementClient(credential=get_credential())


def get_blob_service_client() -> BlobServiceClient:
    account = os.environ["COST_EXPORT_STORAGE_ACCOUNT"]
    suffix = os.environ.get("STORAGE_ENDPOINT_SUFFIX", "core.windows.net")
    return BlobServiceClient(account_url=f"https://{account}.blob.{suffix}", credential=get_credential())


def build_export(period_start: date, period_end: date) -> Export:
    """A one-time, Daily-granularity ActualCost export for a single calendar month.

    Per the tutorial, history is seeded in one-month chunks; the same shape is used to finalise
    a recently-closed month.
    """
    return Export(
        format="Csv",
        partition_data=False,
        delivery_info=ExportDeliveryInfo(
            destination=ExportDeliveryDestination(
                container=os.environ.get("COST_EXPORT_CONTAINER", DEFAULT_EXPORT_CONTAINER),
                root_folder_path="{}/{:%Y-%m}".format(os.environ["TRE_ID"], period_start),
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
            if status in _SUCCESS_STATUSES:
                return latest
            if status and status not in _RUNNING_STATUSES:
                raise ExportRunFailed(f"export '{export_name}' run finished with status '{latest.status}'")
        if time.monotonic() >= deadline:
            raise ExportRunFailed(f"export '{export_name}' did not complete within {timeout_seconds}s")
        time.sleep(poll_seconds)


def download_export_csv(blob_service_client: BlobServiceClient, file_name: str) -> str:
    """Download the CSV a completed export run wrote.

    ``file_name`` from the run history is container-qualified (``<container>/<path>``), so the
    leading container segment is stripped before addressing the blob.
    """
    container = os.environ.get("COST_EXPORT_CONTAINER", DEFAULT_EXPORT_CONTAINER)
    blob_path = file_name.lstrip("/")
    if blob_path.lower().startswith(container.lower() + "/"):
        blob_path = blob_path[len(container) + 1:]
    blob_client = blob_service_client.get_blob_client(container=container, blob=blob_path)
    return blob_client.download_blob(encoding="utf-8-sig").readall()


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


def aggregate_export_rows(csv_text: str) -> List[dict]:
    """Aggregate an export CSV into the rows the API ingest endpoint expects.

    One row is emitted per (date, resource group, tag, currency); a resource carrying several
    TRE tags contributes a row per tag, exactly as the Query API's "group by Tag" does, and an
    untagged resource contributes a single row with an empty tag which the API attributes from
    its resource group.
    """
    aggregated: Dict[Tuple[int, str, str, str], float] = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
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


def ingest_rows(period_start: date, period_end: date, rows: List[dict]) -> dict:
    """Post the aggregated export rows to the TRE API so they are persisted as a final period."""
    api_url = os.environ["TRE_API_URL"].rstrip("/")
    token = get_access_token(os.environ["API_CLIENT_ID"])
    response = requests.post(
        f"{api_url}/api/internal/costs/ingest",
        json={
            "from_date": period_start.isoformat(),
            "to_date": period_end.isoformat(),
            "granularity": "Daily",
            "rows": rows,
        },
        headers={"Authorization": "Bearer " + token},
        timeout=DEFAULT_HTTP_TIMEOUT,
    )
    response.raise_for_status()
    return response.json() if response.content else {}


def export_month(period_start: date, period_end: date,
                 client: Optional[CostManagementClient] = None,
                 blob_service_client: Optional[BlobServiceClient] = None) -> dict:
    """Create, run and ingest a one-time Cost Management export for a single calendar month.

    Returns ``{"rows": n}``; ``rows`` is 0 for a month with no cost data, which is how the
    history walk detects it has reached the start of the data.
    """
    client = client or get_cost_management_client()
    blob_service_client = blob_service_client or get_blob_service_client()
    scope = _export_scope()
    export_name = _export_name(period_start)

    logging.info("Creating cost export '%s' for %s..%s", export_name, period_start, period_end)
    client.exports.create_or_update(scope, export_name, build_export(period_start, period_end))

    submitted_at = datetime.now(timezone.utc)
    client.exports.execute(scope, export_name)
    run = wait_for_export_run(client, scope, export_name, submitted_at)

    if not run.file_name:
        logging.info("Cost export '%s' produced no file; treating month as empty.", export_name)
        rows: List[dict] = []
    else:
        rows = aggregate_export_rows(download_export_csv(blob_service_client, run.file_name))

    result = ingest_rows(period_start, period_end, rows)
    logging.info("Ingested %s aggregated row(s) for %s..%s: %s", len(rows), period_start, period_end, result)
    return {"rows": len(rows), "ingested": result}


def _months_back(count: Optional[int]) -> Iterator[Tuple[date, date]]:
    """Yield (first_day, last_day) for each month, newest first, starting at the previous month."""
    today = datetime.now(timezone.utc).date()
    month_end = _month_bounds(today)[0] - timedelta(days=1)
    produced = 0
    while count is None or produced < count:
        month_first, next_first = _month_bounds(month_end)
        yield month_first, next_first - timedelta(days=1)
        produced += 1
        month_end = month_first - timedelta(days=1)


def finalise_previous_months(look_back_months: int = 1,
                             client: Optional[CostManagementClient] = None,
                             blob_service_client: Optional[BlobServiceClient] = None) -> dict:
    """Re-export recently-closed months so they are finalised in the collection.

    Azure keeps re-rating a month for a while after it closes, so each recently-closed month is
    re-exported and the ingested period overwrites the previous one.
    """
    client = client or get_cost_management_client()
    blob_service_client = blob_service_client or get_blob_service_client()
    months = 0
    for period_start, period_end in _months_back(max(look_back_months, 0)):
        export_month(period_start, period_end, client, blob_service_client)
        months += 1
    return {"months_finalised": months}


def backfill_history(max_months: Optional[int] = None,
                     stop_after_empty_months: int = BACKFILL_STOP_AFTER_EMPTY_MONTHS,
                     max_runtime_seconds: Optional[int] = BACKFILL_MAX_RUNTIME_SECONDS,
                     client: Optional[CostManagementClient] = None,
                     blob_service_client: Optional[BlobServiceClient] = None) -> dict:
    """Seed cost history by exporting one month at a time, walking backwards.

    Follows the tutorial's "execute the requests in one-month chunks" guidance. The walk stops
    after ``stop_after_empty_months`` *consecutive* empty months (so a single idle month does not
    end it early), once ``max_months`` months have been processed, once ``max_runtime_seconds``
    of wall clock has elapsed (export runs are slow - the remaining months are picked up on the
    next scheduled run), or once it reaches Cost Management's ~13 month retention window.
    """
    client = client or get_cost_management_client()
    blob_service_client = blob_service_client or get_blob_service_client()

    limit = min(max_months, BACKFILL_MAX_MONTHS_LIMIT) if max_months else BACKFILL_MAX_MONTHS_LIMIT
    months_processed = 0
    months_with_data = 0
    consecutive_empty = 0
    started_at = time.monotonic()

    for period_start, period_end in _months_back(limit):
        if max_runtime_seconds and (time.monotonic() - started_at) >= max_runtime_seconds:
            logging.info("Backfill reached its wall-clock budget of %ss after %s month(s); "
                         "stopping and resuming on the next scheduled run.",
                         max_runtime_seconds, months_processed)
            break
        result = export_month(period_start, period_end, client, blob_service_client)
        months_processed += 1
        if result["rows"] == 0:
            consecutive_empty += 1
            if consecutive_empty >= stop_after_empty_months:
                logging.info("Backfill reached %s consecutive month(s) with no cost data "
                             "(through %s); stopping.", consecutive_empty, period_start)
                break
        else:
            consecutive_empty = 0
            months_with_data += 1

    logging.info("Cost history backfill finished: %s month(s) processed, %s with data.",
                 months_processed, months_with_data)
    return {"months_processed": months_processed, "months_with_data": months_with_data}
