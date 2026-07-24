from unittest.mock import MagicMock, patch

import azure.functions as func

from CurrentMonthRefreshTrigger import main as current_month_main
from PreviousMonthRefreshTrigger import main as previous_month_main
from BackfillTrigger import main as backfill_main
from shared_code import api_client


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


@patch.dict("os.environ", {}, clear=True)
@patch("BackfillTrigger.api_client.backfill_history")
def test_backfill_trigger_uses_defaults(backfill_mock):
    backfill_mock.return_value = {"months_processed": 0, "months_with_data": 0}

    backfill_main(_timer())

    # unset max_months means walk until no data (None); the other options fall back to the
    # module defaults.
    backfill_mock.assert_called_once_with(
        None,
        api_client.BACKFILL_STOP_AFTER_EMPTY_MONTHS,
        api_client.BACKFILL_MAX_RUNTIME_SECONDS)


@patch.dict("os.environ", {
    "COST_PROCESSOR_BACKFILL_MAX_MONTHS": "5",
    "COST_PROCESSOR_BACKFILL_STOP_AFTER_EMPTY_MONTHS": "4",
    "COST_PROCESSOR_BACKFILL_MAX_RUNTIME_SECONDS": "120",
})
@patch("BackfillTrigger.api_client.backfill_history")
def test_backfill_trigger_uses_configured_values(backfill_mock):
    backfill_mock.return_value = {"months_processed": 5, "months_with_data": 5}

    backfill_main(_timer(past_due=True))

    backfill_mock.assert_called_once_with(5, 4, 120)


@patch.dict("os.environ", {
    "COST_PROCESSOR_BACKFILL_MAX_MONTHS": "0",
    "COST_PROCESSOR_BACKFILL_MAX_RUNTIME_SECONDS": "0",
})
@patch("BackfillTrigger.api_client.backfill_history")
def test_backfill_trigger_treats_zero_as_unlimited(backfill_mock):
    backfill_mock.return_value = {"months_processed": 0, "months_with_data": 0}

    backfill_main(_timer())

    # 0 max_months and 0 runtime both mean "no limit" (None)
    backfill_mock.assert_called_once_with(
        None,
        api_client.BACKFILL_STOP_AFTER_EMPTY_MONTHS,
        None)
