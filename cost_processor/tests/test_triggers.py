from unittest.mock import MagicMock, patch

import azure.functions as func

from CurrentMonthRefreshTrigger import main as current_month_main
from PreviousMonthRefreshTrigger import main as previous_month_main


def _timer(past_due: bool = False) -> func.TimerRequest:
    timer = MagicMock(spec=func.TimerRequest)
    timer.past_due = past_due
    return timer


@patch("CurrentMonthRefreshTrigger.api_client.refresh_current_month")
def test_current_month_trigger_refreshes_current_month(refresh_mock):
    refresh_mock.return_value = {"collected_periods": 1}

    current_month_main(_timer())

    refresh_mock.assert_called_once_with()


@patch("CurrentMonthRefreshTrigger.api_client.refresh_current_month")
def test_current_month_trigger_logs_when_past_due(refresh_mock):
    refresh_mock.return_value = {}

    # past_due should not prevent the refresh from running
    current_month_main(_timer(past_due=True))

    refresh_mock.assert_called_once_with()


@patch.dict("os.environ", {"COST_PROCESSOR_PREVIOUS_MONTHS_LOOK_BACK": "3"})
@patch("PreviousMonthRefreshTrigger.api_client.refresh_previous_months")
def test_previous_month_trigger_uses_configured_look_back(refresh_mock):
    previous_month_main(_timer())

    refresh_mock.assert_called_once_with(3)


@patch.dict("os.environ", {}, clear=True)
@patch("PreviousMonthRefreshTrigger.api_client.refresh_previous_months")
def test_previous_month_trigger_defaults_look_back_to_one(refresh_mock):
    previous_month_main(_timer())

    refresh_mock.assert_called_once_with(1)


@patch.dict("os.environ", {}, clear=True)
@patch("PreviousMonthRefreshTrigger.api_client.refresh_previous_months")
def test_previous_month_trigger_runs_when_past_due(refresh_mock):
    previous_month_main(_timer(past_due=True))

    refresh_mock.assert_called_once_with(1)
