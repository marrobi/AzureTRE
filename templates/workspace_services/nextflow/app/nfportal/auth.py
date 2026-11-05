"""Microsoft Entra ID sign-in with the workspace app registration.

The portal runs the OpenID Connect authorization code flow (with PKCE) itself, like
the Gitea workspace service, because App Service Authentication needs ID token
issuance enabled on the app registration. After sign-in, a signed session cookie
holds the user's object ID, name and workspace app roles. Requests without a
session holding WorkspaceOwner or WorkspaceResearcher are rejected.
"""

import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

OWNER_ROLE = "WorkspaceOwner"
PUBLIC_PATHS = ("/healthz", "/auth/login", "/auth/callback", "/auth/logout", "/favicon.svg")
SESSION_USER = "user"
SESSION_FLOW = "auth_flow"
SESSION_LIFETIME_SECONDS = 8 * 3600


@dataclass(frozen=True)
class User:
    id: str
    name: str
    roles: tuple[str, ...]

    @property
    def is_owner(self) -> bool:
        return OWNER_ROLE in self.roles


DEV_USER = User(id="dev-user", name="Developer", roles=(OWNER_ROLE,))


class AuthClient(Protocol):
    def start(self, redirect_uri: str) -> tuple[str, dict[str, Any]]: ...
    def finish(self, flow: dict[str, Any], query: dict[str, str]) -> dict[str, Any]: ...


class MsalAuthClient:
    def __init__(self, client_id: str, client_secret: str, authority: str, http_client: Any = None) -> None:
        import msal

        self.app = msal.ConfidentialClientApplication(
            client_id, client_credential=client_secret, authority=authority, http_client=http_client
        )

    def start(self, redirect_uri: str) -> tuple[str, dict[str, Any]]:
        # MSAL generates and later checks the state, nonce and PKCE verifier stored in the flow.
        # A form_post callback is a cross-site POST, which would not carry the SameSite=Lax session cookie.
        flow = self.app.initiate_auth_code_flow(scopes=[], redirect_uri=redirect_uri, response_mode="query")
        return flow["auth_uri"], flow

    def finish(self, flow: dict[str, Any], query: dict[str, str]) -> dict[str, Any]:
        result = self.app.acquire_token_by_auth_code_flow(flow, query)
        if "error" in result:
            raise PermissionError(result.get("error_description") or result["error"])
        return result.get("id_token_claims") or {}


def user_from_claims(claims: dict[str, Any], allowed_roles: tuple[str, ...]) -> User | None:
    oid = claims.get("oid")
    roles = tuple(r for r in (claims.get("roles") or []) if isinstance(r, str))
    if not oid or not set(roles) & set(allowed_roles):
        return None
    return User(id=oid, name=claims.get("name") or claims.get("preferred_username") or oid, roles=roles)


def session_user(session: dict[str, Any], allowed_roles: tuple[str, ...]) -> User | None:
    data = session.get(SESSION_USER)
    if not isinstance(data, dict) or data.get("exp", 0) < time.time():
        return None
    user = User(id=data.get("id", ""), name=data.get("name", ""), roles=tuple(data.get("roles") or ()))
    return user if user.id and set(user.roles) & set(allowed_roles) else None


def session_payload(user: User) -> dict[str, Any]:
    return {"id": user.id, "name": user.name, "roles": list(user.roles), "exp": time.time() + SESSION_LIFETIME_SECONDS}


def safe_next(path: str | None) -> str:
    """Only allow same-site relative redirects after sign-in."""
    if not path or not path.startswith("/") or path.startswith("//") or "\\" in path or urlsplit(path).netloc:
        return "/"
    return path


class AuthMiddleware:
    """Requires a signed-in user for everything except PUBLIC_PATHS. Runs inside SessionMiddleware."""

    def __init__(self, app: ASGIApp, allowed_roles: tuple[str, ...], dev_mode: bool = False) -> None:
        self.app = app
        self.allowed_roles = allowed_roles
        self.dev_mode = dev_mode

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return
        user = DEV_USER if self.dev_mode else session_user(HTTPConnection(scope).session, self.allowed_roles)
        if user is None:
            await self._deny(scope, receive, send)
            return
        scope.setdefault("state", {})["user"] = user
        await self.app(scope, receive, send)

    async def _deny(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["path"].startswith(("/api/", "/files/")):
            response = JSONResponse({"detail": "Sign in required"}, status_code=401)
        else:
            target = scope["path"] + (f"?{scope['query_string'].decode()}" if scope.get("query_string") else "")
            response = RedirectResponse(f"/auth/login?next={quote(target)}", status_code=302)
        await response(scope, receive, send)


def no_role_response() -> PlainTextResponse:
    return PlainTextResponse(
        "You are signed in, but you need the WorkspaceOwner or WorkspaceResearcher role in this workspace "
        "to use this service.",
        status_code=403,
    )
