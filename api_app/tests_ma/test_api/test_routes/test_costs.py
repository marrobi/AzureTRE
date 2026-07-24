from datetime import datetime

import pytest
from fastapi import HTTPException, status

from api.routes.costs import validate_report_period
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
    assert ex.value.detail == strings.API_GET_COSTS_FROM_DATE_NEED_TO_BE_BEFORE_TO_DATE


def test_validate_report_period_rejects_missing_to_date():
    with pytest.raises(HTTPException) as ex:
        validate_report_period(datetime(2022, 6, 1), None)
    assert ex.value.status_code == status.HTTP_400_BAD_REQUEST
    assert ex.value.detail == strings.API_GET_COSTS_TO_DATE_NEED_TO_BE_LATER_THEN_FROM_DATE


@pytest.mark.parametrize("from_date,to_date", [
    (datetime(2022, 6, 1), datetime(2022, 1, 1)),  # from after to
    (datetime(2022, 6, 1), datetime(2022, 6, 1)),  # equal
])
def test_validate_report_period_rejects_to_date_not_after_from_date(from_date, to_date):
    with pytest.raises(HTTPException) as ex:
        validate_report_period(from_date, to_date)
    assert ex.value.status_code == status.HTTP_400_BAD_REQUEST
    assert ex.value.detail == strings.API_GET_COSTS_TO_DATE_NEED_TO_BE_LATER_THEN_FROM_DATE
