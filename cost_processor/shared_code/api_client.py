import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple

import requests
from azure.identity import DefaultAzureCredential

# Authenticate to the refresh endpoint with the Cost Processor managed identity: request a
# token for the API's own audience; the API authorises by matching the token's client id.
DEFAULT_HTTP_TIMEOUT = 60


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
        params["from_date"] = from_date.isoformat()
    if to_date is not None:
        params["to_date"] = to_date.isoformat()

    response = requests.post(
        f"{api_url}/api/internal/costs/refresh",
        params=params,
        headers={"Authorization": "Bearer " + token},
        timeout=DEFAULT_HTTP_TIMEOUT,
    )
    response.raise_for_status()
    logging.info("Cost refresh for period %s -> %s returned %s", from_date, to_date, response.status_code)
    return response.json() if response.content else {}


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
