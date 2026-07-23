from datetime import date, datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from shared_code import api_client


@patch.dict("os.environ", {
    "TRE_API_URL": "https://api-test.example.com",
    "API_CLIENT_ID": "api-client-id",
    "MANAGED_IDENTITY_CLIENT_ID": "mi-client-id",
})
@patch("shared_code.api_client.requests.post")
@patch("shared_code.api_client.get_access_token", return_value="a-token")
def test_refresh_period_calls_internal_endpoint_with_bearer_token(get_token_mock, post_mock):
    response = MagicMock()
    response.content = b"{}"
    response.status_code = 202
    response.json.return_value = {"collected_periods": 1}
    post_mock.return_value = response

    api_client.refresh_period(date(2022, 5, 1), date(2022, 5, 31), granularity="Daily")

    get_token_mock.assert_called_once_with("api-client-id")
    args, kwargs = post_mock.call_args
    assert args[0] == "https://api-test.example.com/api/internal/costs/refresh"
    assert kwargs["headers"]["Authorization"] == "Bearer " + "a-token"
    assert kwargs["params"]["granularity"] == "Daily"
    assert kwargs["params"]["from_date"] == "2022-05-01T00:00:00Z"
    assert kwargs["params"]["to_date"] == "2022-05-31T00:00:00Z"


@patch.dict("os.environ", {
    "TRE_API_URL": "https://api-test.example.com/",
    "API_CLIENT_ID": "api-client-id",
})
@patch("shared_code.api_client.requests.post")
@patch("shared_code.api_client.get_access_token", return_value="a-token")
def test_refresh_current_month_sends_no_dates(get_token_mock, post_mock):
    response = MagicMock()
    response.content = b""
    response.status_code = 202
    post_mock.return_value = response

    api_client.refresh_current_month()

    _, kwargs = post_mock.call_args
    assert "from_date" not in kwargs["params"]
    assert "to_date" not in kwargs["params"]
    assert kwargs["params"]["granularity"] == "Daily"


def test_get_access_token_requests_api_audience_scope():
    with patch("shared_code.api_client.get_credential") as get_cred_mock:
        cred = MagicMock()
        cred.get_token.return_value = MagicMock(token="tok")
        get_cred_mock.return_value = cred

        token = api_client.get_access_token("api-client-id")

        cred.get_token.assert_called_once_with("api://api-client-id/.default")
        assert token == "tok"


@patch.dict("os.environ", {
    "TRE_API_URL": "https://api-test.example.com",
    "API_CLIENT_ID": "api-client-id",
})
@patch("shared_code.api_client.requests.post")
@patch("shared_code.api_client.get_access_token", return_value="a-token")
def test_refresh_period_omits_dates_when_none(get_token_mock, post_mock):
    response = MagicMock()
    response.content = b"{}"
    response.json.return_value = {}
    post_mock.return_value = response

    api_client.refresh_period(None, None)

    _, kwargs = post_mock.call_args
    assert "from_date" not in kwargs["params"]
    assert "to_date" not in kwargs["params"]


@patch.dict("os.environ", {
    "TRE_API_URL": "https://api-test.example.com",
    "API_CLIENT_ID": "api-client-id",
})
@patch("shared_code.api_client.requests.post")
@patch("shared_code.api_client.get_access_token", return_value="a-token")
def test_refresh_period_returns_empty_dict_when_no_content(get_token_mock, post_mock):
    response = MagicMock()
    response.content = b""
    post_mock.return_value = response

    result = api_client.refresh_period(date(2022, 5, 1), date(2022, 5, 31))

    assert result == {}
    response.json.assert_not_called()


@patch.dict("os.environ", {
    "TRE_API_URL": "https://api-test.example.com",
    "API_CLIENT_ID": "api-client-id",
})
@patch("shared_code.api_client.requests.post")
@patch("shared_code.api_client.get_access_token", return_value="a-token")
def test_refresh_period_raises_on_http_error(get_token_mock, post_mock):
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("boom")
    post_mock.return_value = response

    with pytest.raises(requests.HTTPError):
        api_client.refresh_period(date(2022, 5, 1), date(2022, 5, 31))


@patch.dict("os.environ", {"MANAGED_IDENTITY_CLIENT_ID": "mi-client-id"}, clear=True)
@patch("shared_code.api_client.DefaultAzureCredential")
def test_get_credential_uses_managed_identity_when_set(credential_mock):
    api_client.get_credential()

    credential_mock.assert_called_once_with(managed_identity_client_id="mi-client-id",
                                            exclude_shared_token_cache_credential=True)


@patch.dict("os.environ", {}, clear=True)
@patch("shared_code.api_client.DefaultAzureCredential")
def test_get_credential_falls_back_to_default_when_not_set(credential_mock):
    api_client.get_credential()

    credential_mock.assert_called_once_with()


@pytest.mark.parametrize("reference,expected_first,expected_next_first", [
    (date(2022, 5, 14), date(2022, 5, 1), date(2022, 6, 1)),
    # December must roll the year over, not the month
    (date(2022, 12, 3), date(2022, 12, 1), date(2023, 1, 1)),
    (date(2022, 1, 31), date(2022, 1, 1), date(2022, 2, 1)),
])
def test_month_bounds(reference, expected_first, expected_next_first):
    first, next_first = api_client._month_bounds(reference)

    assert first == expected_first
    assert next_first == expected_next_first


@patch("shared_code.api_client.refresh_period")
@patch("shared_code.api_client.datetime")
def test_refresh_previous_months_refreshes_single_previous_month(datetime_mock, refresh_period_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)

    api_client.refresh_previous_months(1)

    refresh_period_mock.assert_called_once_with(date(2026, 6, 1), date(2026, 6, 30), granularity="Daily")


@patch("shared_code.api_client.refresh_period")
@patch("shared_code.api_client.datetime")
def test_refresh_previous_months_walks_back_multiple_months(datetime_mock, refresh_period_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)

    api_client.refresh_previous_months(3)

    assert refresh_period_mock.call_args_list == [
        call(date(2026, 6, 1), date(2026, 6, 30), granularity="Daily"),
        call(date(2026, 5, 1), date(2026, 5, 31), granularity="Daily"),
        call(date(2026, 4, 1), date(2026, 4, 30), granularity="Daily"),
    ]


@patch("shared_code.api_client.refresh_period")
@patch("shared_code.api_client.datetime")
def test_refresh_previous_months_crosses_year_boundary(datetime_mock, refresh_period_mock):
    # In January the previous months are in the prior year.
    datetime_mock.now.return_value = datetime(2026, 1, 10, tzinfo=timezone.utc)

    api_client.refresh_previous_months(2)

    assert refresh_period_mock.call_args_list == [
        call(date(2025, 12, 1), date(2025, 12, 31), granularity="Daily"),
        call(date(2025, 11, 1), date(2025, 11, 30), granularity="Daily"),
    ]


@patch("shared_code.api_client.refresh_period")
@patch("shared_code.api_client.datetime")
def test_refresh_previous_months_zero_look_back_does_nothing(datetime_mock, refresh_period_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)

    api_client.refresh_previous_months(0)

    refresh_period_mock.assert_not_called()


@patch.dict("os.environ", {
    "TRE_API_URL": "https://api-test.example.com",
    "API_CLIENT_ID": "api-client-id",
})
@patch("shared_code.api_client.requests.post")
@patch("shared_code.api_client.get_access_token", return_value="a-token")
def test_refresh_period_raises_throttled_on_429(get_token_mock, post_mock):
    response = MagicMock()
    response.status_code = 429
    response.headers = {"Retry-After": "30"}
    post_mock.return_value = response

    with pytest.raises(api_client.CostRefreshThrottled) as exc:
        api_client.refresh_period(date(2022, 5, 1), date(2022, 5, 31))

    assert exc.value.retry_after == 30
    response.raise_for_status.assert_not_called()


@patch("shared_code.api_client.refresh_period")
@patch("shared_code.api_client.datetime")
def test_backfill_history_walks_back_until_no_data(datetime_mock, refresh_period_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    refresh_period_mock.side_effect = [
        {"collected_periods": 1, "total_rows": 5},   # June - has data
        {"collected_periods": 1, "total_rows": 3},   # May - has data
        {"collected_periods": 1, "total_rows": 0},   # April - no data (1 consecutive)
        {"collected_periods": 1, "total_rows": 0},   # March - no data (2 consecutive) -> stop
    ]

    summary = api_client.backfill_history()

    assert refresh_period_mock.call_args_list == [
        call(date(2026, 6, 1), date(2026, 6, 30), granularity="Daily"),
        call(date(2026, 5, 1), date(2026, 5, 31), granularity="Daily"),
        call(date(2026, 4, 1), date(2026, 4, 30), granularity="Daily"),
        call(date(2026, 3, 1), date(2026, 3, 31), granularity="Daily"),
    ]
    assert summary == {"months_processed": 4, "months_with_data": 2}


@patch("shared_code.api_client.refresh_period")
@patch("shared_code.api_client.datetime")
def test_backfill_history_continues_past_single_empty_month(datetime_mock, refresh_period_mock):
    # A single idle (zero-cost) month in the middle of history must NOT stop the walk - only
    # `stop_after_empty_months` consecutive empties do - so older data is not silently skipped.
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    refresh_period_mock.side_effect = [
        {"collected_periods": 1, "total_rows": 5},   # June - data
        {"collected_periods": 1, "total_rows": 0},   # May - empty (1)
        {"collected_periods": 1, "total_rows": 7},   # April - data -> resets the counter
        {"collected_periods": 1, "total_rows": 0},   # March - empty (1)
        {"collected_periods": 1, "total_rows": 0},   # February - empty (2 consecutive) -> stop
    ]

    summary = api_client.backfill_history()

    assert refresh_period_mock.call_count == 5
    assert summary == {"months_processed": 5, "months_with_data": 2}


@patch("shared_code.api_client.refresh_period")
@patch("shared_code.api_client.datetime")
def test_backfill_history_respects_max_months(datetime_mock, refresh_period_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    refresh_period_mock.return_value = {"collected_periods": 1, "total_rows": 5}

    summary = api_client.backfill_history(max_months=2)

    assert refresh_period_mock.call_count == 2
    assert summary == {"months_processed": 2, "months_with_data": 2}


@patch("shared_code.api_client.time.sleep")
@patch("shared_code.api_client.refresh_period")
@patch("shared_code.api_client.datetime")
def test_backfill_history_retries_on_throttle(datetime_mock, refresh_period_mock, sleep_mock):
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    refresh_period_mock.side_effect = [
        api_client.CostRefreshThrottled(7),          # June throttled...
        {"collected_periods": 1, "total_rows": 4},   # ...retried, has data
        {"collected_periods": 1, "total_rows": 0},   # May - no data -> stop
    ]

    summary = api_client.backfill_history(stop_after_empty_months=1)

    sleep_mock.assert_called_once_with(7)
    assert summary == {"months_processed": 2, "months_with_data": 1}


@patch("shared_code.api_client.time.sleep")
@patch("shared_code.api_client.refresh_period")
@patch("shared_code.api_client.datetime")
def test_backfill_history_surfaces_failure_instead_of_silent_gap(datetime_mock, refresh_period_mock, sleep_mock):
    # One month imports fine, the next fails hard (not a throttle). The backfill must NOT treat the
    # failure as "no data / reached the start of history" and stop silently - it must raise so the
    # run is recorded as failed and retried, leaving no undetected gap in the collected history.
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    refresh_period_mock.side_effect = [
        {"collected_periods": 1, "total_rows": 5},
        requests.HTTPError("500 Server Error"),
    ]

    with pytest.raises(requests.HTTPError):
        api_client.backfill_history()

    # it did not swallow the error and stop early as if it had reached the end of the data
    assert refresh_period_mock.call_count == 2
    sleep_mock.assert_not_called()


@patch("shared_code.api_client.time.sleep")
@patch("shared_code.api_client.refresh_period")
@patch("shared_code.api_client.datetime")
def test_backfill_history_gives_up_after_persistent_throttling(datetime_mock, refresh_period_mock, sleep_mock):
    # Persistent throttling eventually surfaces as a failed run (a visible gap), never a silent stop.
    datetime_mock.now.return_value = datetime(2026, 7, 19, tzinfo=timezone.utc)
    refresh_period_mock.side_effect = api_client.CostRefreshThrottled(1)

    with pytest.raises(api_client.CostRefreshThrottled):
        api_client.backfill_history()

    assert sleep_mock.call_count == api_client.BACKFILL_THROTTLE_MAX_RETRIES
