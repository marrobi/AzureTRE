from datetime import date
from unittest.mock import MagicMock, patch

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
