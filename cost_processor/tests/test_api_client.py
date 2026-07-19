from datetime import date
from unittest.mock import MagicMock, patch

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
    assert kwargs["params"]["from_date"] == "2022-05-01"
    assert kwargs["params"]["to_date"] == "2022-05-31"


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
