from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status

from api.routes.costs import ingest_costs, validate_report_period
from models.domain.costs import CostIngestRequest, ExportedCostRow
from resources import strings


def test_validate_report_period_allows_month_to_date():
    # both dates omitted is the valid month-to-date report and must not raise
    validate_report_period(None, None)


def test_validate_report_period_allows_valid_range():
    validate_report_period(datetime(2022, 1, 1), datetime(2022, 6, 1))


def test_validate_report_period_allows_multi_year_range():
    # the previous 1-year cap has been removed; multi-year ranges are valid
    validate_report_period(datetime(2022, 1, 1), datetime(2025, 1, 1))


def test_validate_report_period_rejects_missing_from_date():
    # to_date without from_date must return a clean 400 (previously raised a TypeError -> 500)
    with pytest.raises(HTTPException) as ex:
        validate_report_period(None, datetime(2022, 6, 1))
    assert ex.value.status_code == status.HTTP_400_BAD_REQUEST
    assert ex.value.detail == strings.API_GET_COSTS_FROM_DATE_REQUIRED


def test_validate_report_period_rejects_missing_to_date():
    with pytest.raises(HTTPException) as ex:
        validate_report_period(datetime(2022, 6, 1), None)
    assert ex.value.status_code == status.HTTP_400_BAD_REQUEST
    assert ex.value.detail == strings.API_GET_COSTS_TO_DATE_REQUIRED


@pytest.mark.parametrize("from_date,to_date", [
    (datetime(2022, 6, 1), datetime(2022, 1, 1)),  # from after to
    (datetime(2022, 6, 1), datetime(2022, 6, 1)),  # equal
])
def test_validate_report_period_rejects_to_date_not_after_from_date(from_date, to_date):
    with pytest.raises(HTTPException) as ex:
        validate_report_period(from_date, to_date)
    assert ex.value.status_code == status.HTTP_400_BAD_REQUEST
    assert ex.value.detail == strings.API_GET_COSTS_TO_DATE_NEED_TO_BE_LATER_THEN_FROM_DATE


@pytest.mark.asyncio
async def test_ingest_costs_persists_the_exported_period():
    cost_service = AsyncMock()
    cost_service.ingest_export_costs.return_value = {"collected_periods": 3, "total_rows": 9}
    payload = CostIngestRequest(
        from_date=date(2022, 5, 1), to_date=date(2022, 5, 31),
        subscription_id="sub-2",
        rows=[ExportedCostRow(date=20220501, resource_group="rg", tag='"tre_id":"guy22"',
                              cost=1.0, currency="USD")])

    response = await ingest_costs(payload, cost_service, AsyncMock(), AsyncMock())

    assert response.status_code == status.HTTP_202_ACCEPTED
    args = cost_service.ingest_export_costs.await_args.args
    # dates are widened to datetimes so they key the collection the same way queried periods do
    assert args[2] == datetime(2022, 5, 1)
    assert args[3] == datetime(2022, 5, 31)
    assert args[4] == payload.rows
    # the export covered one subscription, so the rows are only attributed to that one
    assert args[7] == "sub-2"


@pytest.mark.asyncio
async def test_ingest_costs_accepts_a_single_day_period():
    # the period is an inclusive range of days, so a one-day chunk of a large month is valid
    cost_service = AsyncMock()
    cost_service.ingest_export_costs.return_value = {"collected_periods": 1, "total_rows": 1}

    response = await ingest_costs(
        CostIngestRequest(from_date=date(2022, 5, 1), to_date=date(2022, 5, 1)),
        cost_service, AsyncMock(), AsyncMock())

    assert response.status_code == status.HTTP_202_ACCEPTED
    cost_service.ingest_export_costs.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_costs_rejects_an_invalid_period():
    cost_service = AsyncMock()

    with pytest.raises(HTTPException) as ex:
        await ingest_costs(CostIngestRequest(from_date=date(2022, 6, 1), to_date=date(2022, 1, 1)),
                           cost_service, AsyncMock(), AsyncMock())

    assert ex.value.status_code == status.HTTP_400_BAD_REQUEST
    assert ex.value.detail == strings.API_INGEST_COSTS_TO_DATE_BEFORE_FROM_DATE
    cost_service.ingest_export_costs.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingest_costs_returns_500_when_ingestion_fails():
    cost_service = AsyncMock()
    cost_service.ingest_export_costs.side_effect = Exception("boom")

    with pytest.raises(HTTPException) as ex:
        await ingest_costs(CostIngestRequest(from_date=date(2022, 5, 1), to_date=date(2022, 5, 31)),
                           cost_service, AsyncMock(), AsyncMock())

    assert ex.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert ex.value.detail == strings.API_INGEST_COSTS_INTERNAL_SERVER_ERROR
