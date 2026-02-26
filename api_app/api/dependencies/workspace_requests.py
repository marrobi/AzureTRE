from fastapi import Depends, HTTPException, Path, status
from pydantic import UUID4

from api.helpers import get_repository
from db.repositories.workspace_requests import WorkspaceRequestRepository
from models.domain.workspace_request import WorkspaceRequest
from db.errors import EntityDoesNotExist, UnableToAccessDatabase
from resources import strings


async def get_workspace_request_by_id(workspace_request_id: UUID4, workspace_request_repo: WorkspaceRequestRepository) -> WorkspaceRequest:
    try:
        return await workspace_request_repo.get_workspace_request_by_id(workspace_request_id)
    except EntityDoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=strings.WORKSPACE_REQUEST_DOES_NOT_EXIST)
    except UnableToAccessDatabase:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=strings.STATE_STORE_ENDPOINT_NOT_RESPONDING)


async def get_workspace_request_by_id_from_path(workspace_request_id: UUID4 = Path(...), workspace_request_repo=Depends(get_repository(WorkspaceRequestRepository))) -> WorkspaceRequest:
    return await get_workspace_request_by_id(workspace_request_id, workspace_request_repo)
