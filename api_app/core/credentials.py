from contextlib import asynccontextmanager
from core.config import MANAGED_IDENTITY_CLIENT_ID, AAD_AUTHORITY_URL
from azure.core.credentials import TokenCredential
from urllib.parse import urlparse

from azure.identity import (
    DefaultAzureCredential,
    ManagedIdentityCredential,
    ChainedTokenCredential,
    ClientAssertionCredential,
)
from azure.identity.aio import (
    DefaultAzureCredential as DefaultAzureCredentialASync,
    ManagedIdentityCredential as ManagedIdentityCredentialASync,
    ChainedTokenCredential as ChainedTokenCredentialASync,
)


# Audience used when exchanging the core API managed identity token for the
# Token-exchange audience for federating as the airlock signer; differs per sovereign cloud.
def _get_token_exchange_audience() -> str:
    authority = urlparse(AAD_AUTHORITY_URL).netloc.lower()
    if authority.endswith(".us"):
        return "api://AzureADTokenExchangeUSGov/.default"  # nosec B105 - token exchange audience, not a secret
    if authority.endswith(".cn"):
        return "api://AzureADTokenExchangeChina/.default"  # nosec B105 - token exchange audience, not a secret
    return "api://AzureADTokenExchange/.default"  # nosec B105 - token exchange audience, not a secret


def get_credential() -> TokenCredential:
    if MANAGED_IDENTITY_CLIENT_ID:
        return ChainedTokenCredential(
            ManagedIdentityCredential(client_id=MANAGED_IDENTITY_CLIENT_ID)
        )
    else:
        return DefaultAzureCredential(authority=urlparse(AAD_AUTHORITY_URL).netloc,
                                      exclude_shared_token_cache_credential=True,
                                      exclude_workload_identity_credential=True,
                                      exclude_developer_cli_credential=True,
                                      exclude_managed_identity_credential=True,
                                      exclude_powershell_credential=True
                                      )


async def get_credential_async():
    return (
        ChainedTokenCredentialASync(
            ManagedIdentityCredentialASync(client_id=MANAGED_IDENTITY_CLIENT_ID)
        )
        if MANAGED_IDENTITY_CLIENT_ID
        else DefaultAzureCredentialASync(authority=urlparse(AAD_AUTHORITY_URL).netloc,
                                         exclude_shared_token_cache_credential=True,
                                         exclude_workload_identity_credential=True,
                                         exclude_developer_cli_credential=True,
                                         exclude_managed_identity_credential=True,
                                         exclude_powershell_credential=True
                                         )
    )


def get_airlock_signer_credential(signer_client_id: str, tenant_id: str) -> TokenCredential:
    """Credential that authenticates as the per-workspace airlock SAS signer via workload identity
    federation from the core API managed identity. See docs/azure-tre-overview/airlock.md (SAS signing).
    """
    managed_identity = ManagedIdentityCredential(client_id=MANAGED_IDENTITY_CLIENT_ID)

    def _get_managed_identity_assertion() -> str:
        return managed_identity.get_token(_get_token_exchange_audience()).token

    return ClientAssertionCredential(
        tenant_id=tenant_id,
        client_id=signer_client_id,
        func=_get_managed_identity_assertion,
        authority=urlparse(AAD_AUTHORITY_URL).netloc,
    )


@asynccontextmanager
async def get_credential_async_context() -> TokenCredential:
    """
    Context manager which yields the default credentials.
    """
    credential = await get_credential_async()
    yield credential
    await credential.close()
