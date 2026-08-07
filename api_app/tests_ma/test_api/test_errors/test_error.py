import pytest

from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport
from starlette.status import HTTP_404_NOT_FOUND, HTTP_401_UNAUTHORIZED

from api.errors.http_error import http_error_handler

pytestmark = pytest.mark.asyncio


async def test_frw_validation_error_format(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/wrong_path/asd")

    assert response.status_code == HTTP_404_NOT_FOUND

    assert "Not Found" in response.text


async def test_http_error_handler_propagates_headers():
    exc = HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="nope",
                        headers={"WWW-Authenticate": "Bearer"})

    response = http_error_handler(None, exc)

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.headers.get("WWW-Authenticate") == "Bearer"
