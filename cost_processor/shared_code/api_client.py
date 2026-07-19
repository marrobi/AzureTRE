import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests
from azure.identity import DefaultAzureCredential

# The refresh endpoint is authenticated with the Cost Processor managed identity, which holds
# the TRECostProcessor application role on the TRE API app registration. We request a token for
# the API's own audience so the resulting token carries that role in its `roles` claim.
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


def _month_bounds(reference: date):
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
    """Refresh the still-settling current month (month-to-date)."""
    first, _ = _month_bounds(datetime.now(timezone.utc).date())
    return refresh_period(first, None, granularity="Daily")


def refresh_previous_months(look_back_months: int = 1) -> None:
    """Sweep the recently-closed months so they are finalised in the collection.

    Older completed months are immutable and marked final by the API, so this only needs to
    cover the window during which the just-closed month is still being re-rated by Azure.
    """
    today = datetime.now(timezone.utc).date()
    current_first, _ = _month_bounds(today)
    for i in range(1, look_back_months + 1):
        # step back i months from the first of the current month
        month_end = current_first - timedelta(days=1)
        for _ in range(i - 1):
            month_end = month_end.replace(day=1) - timedelta(days=1)
        month_first, next_first = _month_bounds(month_end)
        refresh_period(month_first, next_first - timedelta(days=1), granularity="Daily")
