"""Query-API helpers for the *current* (still-settling) month.

Closed months - history backfill and month finalisation - are collected from Cost Management
exports instead; see ``exports_client``.
"""

import logging
import os
from datetime import date
from typing import Optional, Tuple

import requests
from azure.identity import DefaultAzureCredential

# Authenticate to the refresh endpoint with the Cost Processor managed identity: request a
# token for the API's own audience; the API authorises by matching the token's client id.
DEFAULT_HTTP_TIMEOUT = 60


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


def get_subscription_ids() -> list:
    """Subscriptions TRE costs are incurred in, core first.

    A Cost Management export only ever covers one subscription, and workspaces can be deployed to
    their own, so the API (which owns the workspace records) is asked which ones to export.
    """
    api_url = os.environ["TRE_API_URL"].rstrip("/")
    token = get_access_token(os.environ["API_CLIENT_ID"])
    response = requests.get(
        f"{api_url}/api/internal/costs/subscriptions",
        headers={"Authorization": "Bearer " + token},
        timeout=DEFAULT_HTTP_TIMEOUT,
    )
    response.raise_for_status()
    subscription_ids = (response.json() or {}).get("subscription_ids") or []
    core_subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    if core_subscription_id not in subscription_ids:
        subscription_ids = [core_subscription_id] + list(subscription_ids)
    return list(subscription_ids)


def refresh_current_month() -> dict:
    """Refresh the still-settling current month (month-to-date).

    Sends no dates so the API uses its month-to-date timeframe; a start date with no end
    date is rejected by the endpoint's period validation.
    """
    return refresh_period(None, None, granularity="Daily")
