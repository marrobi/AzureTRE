import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple

import requests
from azure.identity import DefaultAzureCredential

# Authenticate to the refresh endpoint with the Cost Processor managed identity: request a
# token for the API's own audience; the API authorises by matching the token's client id.
DEFAULT_HTTP_TIMEOUT = 60

# How many times a single month is retried while the API/Cost Management is throttling (429)
# before the backfill run gives up and fails (to be resumed on its next schedule).
BACKFILL_THROTTLE_MAX_RETRIES = 6

# Stop the history walk only after this many *consecutive* empty months, so a single idle
# (zero-cost) month mid-history doesn't prematurely end the backfill and leave older data behind.
BACKFILL_STOP_AFTER_EMPTY_MONTHS = 2

# Overall wall-clock budget (seconds) for a single backfill run. The Cost Processor runs on a
# single-worker plan and a month can sleep through repeated throttling (429), so a run is capped
# to avoid tying the worker up for a long time - it simply resumes on its next scheduled run.
BACKFILL_MAX_RUNTIME_SECONDS = 1800


class CostRefreshThrottled(Exception):
    """Raised when the refresh endpoint reports throttling (HTTP 429); carries retry-after seconds."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"cost refresh throttled, retry after {retry_after}s")
        self.retry_after = retry_after


def get_credential() -> DefaultAzureCredential:
    managed_identity = os.environ.get("MANAGED_IDENTITY_CLIENT_ID")
    if managed_identity:
        return DefaultAzureCredential(managed_identity_client_id=managed_identity,
                                      exclude_shared_token_cache_credential=True)
    return DefaultAzureCredential()


def get_access_token(api_client_id: str) -> str:
    credential = get_credential()
    scope = f"api://{api_client_id}/.default"
    return credential.get_token(scope).token


def _month_bounds(reference: date) -> Tuple[date, date]:
    """Return (first_day_of_month, first_day_of_next_month) for the month containing reference."""
    first = reference.replace(day=1)
    if first.month == 12:
        next_first = first.replace(year=first.year + 1, month=1)
    else:
        next_first = first.replace(month=first.month + 1)
    return first, next_first


def refresh_period(from_date: Optional[date], to_date: Optional[date], granularity: str = "Daily") -> dict:
    """Call the TRE API internal cost refresh endpoint for the given period using managed identity."""
    api_url = os.environ["TRE_API_URL"].rstrip("/")
    api_client_id = os.environ["API_CLIENT_ID"]

    token = get_access_token(api_client_id)
    params = {"granularity": granularity}
    if from_date is not None:
        params["from_date"] = from_date.isoformat() + "T00:00:00Z"
    if to_date is not None:
        params["to_date"] = to_date.isoformat() + "T00:00:00Z"

    response = requests.post(
        f"{api_url}/api/internal/costs/refresh",
        params=params,
        headers={"Authorization": "Bearer " + token},
        timeout=DEFAULT_HTTP_TIMEOUT,
    )
    if response.status_code == 429:
        # Cost Management is throttling; surface the retry-after so the caller can wait it out
        # rather than treating it as a hard failure.
        raise CostRefreshThrottled(_retry_after_seconds(response))
    response.raise_for_status()
    logging.info("Cost refresh for period %s -> %s returned %s", from_date, to_date, response.status_code)
    return response.json() if response.content else {}


def _retry_after_seconds(response, default: int = 60) -> int:
    try:
        return int(response.headers.get("Retry-After", default))
    except (TypeError, ValueError):
        return default


def refresh_current_month() -> dict:
    """Refresh the still-settling current month (month-to-date).

    Sends no dates so the API uses its month-to-date timeframe; a start date with no end
    date is rejected by the endpoint's period validation.
    """
    return refresh_period(None, None, granularity="Daily")


def refresh_previous_months(look_back_months: int = 1) -> None:
    """Sweep recently-closed months so they are finalised in the collection."""
    today = datetime.now(timezone.utc).date()
    # Start from the last day of the month before the current one and step back a month at a time.
    month_end = _month_bounds(today)[0] - timedelta(days=1)
    for _ in range(look_back_months):
        month_first, next_first = _month_bounds(month_end)
        refresh_period(month_first, next_first - timedelta(days=1), granularity="Daily")
        # move to the last day of the preceding month
        month_end = month_first - timedelta(days=1)


def _refresh_month_with_retry(month_first: date, month_last: date,
                              max_retries: int = BACKFILL_THROTTLE_MAX_RETRIES) -> dict:
    """Refresh a single month, waiting out throttling (429) up to ``max_retries`` times.

    Only throttling is retried; any other error propagates so the backfill run fails loudly
    (and resumes on its next schedule) rather than silently skipping - and gapping - a month.
    """
    attempt = 0
    while True:
        try:
            return refresh_period(month_first, month_last, granularity="Daily")
        except CostRefreshThrottled as throttled:
            attempt += 1
            if attempt > max_retries:
                raise
            logging.warning("Backfill throttled for %s..%s; waiting %ss (retry %s/%s).",
                            month_first, month_last, throttled.retry_after, attempt, max_retries)
            time.sleep(throttled.retry_after)


def backfill_history(max_months: Optional[int] = None,
                     stop_after_empty_months: int = BACKFILL_STOP_AFTER_EMPTY_MONTHS,
                     max_runtime_seconds: Optional[int] = BACKFILL_MAX_RUNTIME_SECONDS) -> dict:
    """Walk months backwards from the previous month, persisting each, until enough consecutive
    months have no data to mark the start of history.

    Idempotent: months already finalised in the collection are reused by the API, so re-runs are
    cheap and resume where a throttled or failed earlier run stopped. The walk stops only after
    ``stop_after_empty_months`` *consecutive* empty months, so a single idle (zero-cost) month
    mid-history does not prematurely end it and leave older data un-backfilled. It also stops once
    ``max_runtime_seconds`` of wall-clock time has elapsed (a positive value; ``None``/``0`` means
    no limit) so a run cannot tie up the single worker indefinitely when Cost Management is
    persistently throttling - the remaining months are picked up on the next scheduled run. Any
    error (after retrying throttles) propagates so a failed import surfaces as a failed run instead
    of silently leaving a gap in the collected history.
    """
    today = datetime.now(timezone.utc).date()
    # The current and previous months are covered by their own timers; start at the previous
    # month so nothing between it and the start of history can be skipped.
    month_end = _month_bounds(today)[0] - timedelta(days=1)
    months_processed = 0
    months_with_data = 0
    consecutive_empty = 0
    started_at = time.monotonic()
    while max_months is None or months_processed < max_months:
        if max_runtime_seconds and (time.monotonic() - started_at) >= max_runtime_seconds:
            logging.info("Backfill reached its wall-clock budget of %ss after %s month(s); "
                         "stopping and resuming on the next scheduled run.",
                         max_runtime_seconds, months_processed)
            break
        month_first, next_first = _month_bounds(month_end)
        month_last = next_first - timedelta(days=1)
        result = _refresh_month_with_retry(month_first, month_last)
        months_processed += 1
        if int(result.get("total_rows", 0)) == 0:
            consecutive_empty += 1
            if consecutive_empty >= stop_after_empty_months:
                logging.info("Backfill reached %s consecutive month(s) with no cost data "
                             "(through %s); stopping.", consecutive_empty, month_first)
                break
        else:
            consecutive_empty = 0
            months_with_data += 1
        month_end = month_first - timedelta(days=1)
    logging.info("Cost history backfill finished: %s month(s) processed, %s with data.",
                 months_processed, months_with_data)
    return {"months_processed": months_processed, "months_with_data": months_with_data}
