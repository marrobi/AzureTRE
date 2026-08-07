import logging
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

import config
from helpers import get_admin_token
from resources import strings


pytestmark = pytest.mark.asyncio(loop_scope="session")

LOGGER = logging.getLogger(__name__)

# Cost Management keeps re-rating recent usage, so report on a window that has already settled.
REPORT_TO_DATE = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)
REPORT_FROM_DATE = REPORT_TO_DATE - timedelta(days=3)


def __period_params(granularity: str) -> dict:
    return {
        "granularity": granularity,
        "from_date": REPORT_FROM_DATE.isoformat(),
        "to_date": REPORT_TO_DATE.isoformat(),
    }


async def __get_costs(client: AsyncClient, token: str, params: dict):
    response = await client.get(
        f"{config.TRE_URL}{strings.API_COSTS}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=120)

    # Cost Management throttles aggressively and the answer is out of the TRE's control, so a
    # throttled response is a pass for the API contract but there is nothing further to assert on.
    if response.status_code in (429, 503):
        pytest.skip(f"Azure Cost Management is throttling: {response.status_code}")

    return response


def __total(report: dict) -> float:
    """Sum every cost value in a report, whatever granularity it was returned at."""
    return round(sum(cost["cost"] for cost in report["core_services"]), 2)


@pytest.mark.smoke
async def test_get_costs_returns_a_report(verify) -> None:
    async with AsyncClient(verify=verify) as client:
        token = await get_admin_token(verify=verify)

        response = await __get_costs(client, token, __period_params("None"))

        assert response.status_code == 200
        report = response.json()
        assert "core_services" in report
        assert "shared_services" in report
        assert "workspaces" in report


@pytest.mark.smoke
async def test_get_costs_is_consistent_across_granularities(verify) -> None:
    """The same period must cost the same however it is sliced.

    Daily and Monthly reports are derived from the same collected daily data as the ungranular
    report, so a mismatch means the aggregation or the collection read path has regressed.
    """
    async with AsyncClient(verify=verify) as client:
        token = await get_admin_token(verify=verify)

        totals = {}
        for granularity in ("None", "Daily", "Monthly"):
            response = await __get_costs(client, token, __period_params(granularity))
            assert response.status_code == 200, f"{granularity}: {response.text}"
            totals[granularity] = __total(response.json())

        LOGGER.info(f"core services costs by granularity: {totals}")
        assert totals["Daily"] == pytest.approx(totals["None"], abs=0.01)
        assert totals["Monthly"] == pytest.approx(totals["None"], abs=0.01)


@pytest.mark.smoke
async def test_get_costs_is_repeatable(verify) -> None:
    """A settled period must not change between calls, whether served live, cached or collected."""
    async with AsyncClient(verify=verify) as client:
        token = await get_admin_token(verify=verify)

        first = await __get_costs(client, token, __period_params("Daily"))
        assert first.status_code == 200
        second = await __get_costs(client, token, __period_params("Daily"))
        assert second.status_code == 200

        assert __total(second.json()) == pytest.approx(__total(first.json()), abs=0.01)


@pytest.mark.smoke
@pytest.mark.parametrize("params", [
    {"from_date": REPORT_FROM_DATE.isoformat()},  # to_date missing
    {"to_date": REPORT_TO_DATE.isoformat()},  # from_date missing
    {"from_date": REPORT_TO_DATE.isoformat(), "to_date": REPORT_FROM_DATE.isoformat()},  # inverted
])
async def test_get_costs_rejects_an_invalid_period(verify, params) -> None:
    async with AsyncClient(verify=verify) as client:
        token = await get_admin_token(verify=verify)

        response = await client.get(
            f"{config.TRE_URL}{strings.API_COSTS}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=120)

        assert response.status_code == 400


@pytest.mark.smoke
async def test_get_workspace_costs_returns_404_for_an_unknown_workspace(verify) -> None:
    async with AsyncClient(verify=verify) as client:
        token = await get_admin_token(verify=verify)

        response = await client.get(
            f"{config.TRE_URL}{strings.API_WORKSPACES}/00000000-0000-0000-0000-000000000000/costs",
            headers={"Authorization": f"Bearer {token}"},
            params=__period_params("None"),
            timeout=120)

        assert response.status_code == 404


@pytest.mark.smoke
async def test_get_costs_requires_authentication(verify) -> None:
    async with AsyncClient(verify=verify) as client:
        response = await client.get(f"{config.TRE_URL}{strings.API_COSTS}", timeout=120)

        assert response.status_code in (401, 403)


@pytest.mark.smoke
async def test_ingest_costs_rejects_a_user_token(verify) -> None:
    """The ingest endpoint is for the Cost Processor's managed identity only.

    A TRE admin's delegated token must not be able to write cost data.
    """
    async with AsyncClient(verify=verify) as client:
        token = await get_admin_token(verify=verify)

        response = await client.post(
            f"{config.TRE_URL}{strings.API_INGEST_COSTS}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "tre_id": config.TRE_ID,
                "granularity": "Daily",
                "from_date": REPORT_FROM_DATE.isoformat(),
                "to_date": REPORT_TO_DATE.isoformat(),
                "rows": [],
            },
            timeout=120)

        assert response.status_code in (401, 403)


@pytest.mark.smoke
async def test_cost_subscriptions_rejects_a_user_token(verify) -> None:
    """The subscription list is for the Cost Processor's managed identity only."""
    async with AsyncClient(verify=verify) as client:
        token = await get_admin_token(verify=verify)

        response = await client.get(
            f"{config.TRE_URL}{strings.API_COST_SUBSCRIPTIONS}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=120)

        assert response.status_code in (401, 403)
