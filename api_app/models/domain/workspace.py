from enum import Enum
from pydantic import Field
from models.domain.azuretremodel import AzureTREModel
from models.domain.resource import Resource, ResourceType


class WorkspaceRole(Enum):
    NoRole = 0
    Researcher = 1
    Owner = 2
    AirlockManager = 3


class Workspace(Resource):
    """
    Workspace request
    """
    workspaceURL: str = Field("", title="Workspace URL", description="Main endpoint for workspace users")
    resourceType: ResourceType = ResourceType.Workspace


class WorkspaceAuth(AzureTREModel):
    scopeId: str = Field("", title="Scope ID", description="The Workspace App Scope Id to use for auth")


class WorkspaceAuthConfig(AzureTREModel):
    """Authentication configuration for a workspace, used by shared services."""
    clientId: str = Field("", title="Client ID", description="The OAuth2 client ID for the workspace application registration")
    scopeId: str = Field("", title="Scope ID", description="The Workspace App Scope Id to use for auth")
    issuer: str = Field("", title="Issuer", description="The OAuth2 issuer URL")
    jwksEndpoint: str = Field("", title="JWKS Endpoint", description="The JSON Web Key Set endpoint URL")
