from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status as status_code

from jsonschema.exceptions import ValidationError
from api.helpers import get_repository
from db.repositories.workspace_requests import WorkspaceRequestRepository

from api.dependencies.workspace_requests import get_workspace_request_by_id_from_path
from models.domain.workspace_request import WorkspaceRequestStatus
from models.schemas.workspace_request import (
    WorkspaceRequestInCreate, WorkspaceRequestWithAllowedUserActions,
    WorkspaceRequestWithAllowedUserActionsInList, WorkspaceRequestReviewInCreate
)
from resources import strings
from services.authentication import get_current_tre_user_or_tre_admin, get_current_admin_user, get_current_tre_user

from services.workspace_requests import (
    save_workspace_request, update_workspace_request,
    review_workspace_request as review_workspace_request_service,
    get_allowed_actions, enrich_requests_with_allowed_actions
)
from services.logging import logger

workspace_requests_core_router = APIRouter(dependencies=[Depends(get_current_tre_user_or_tre_admin)])


def _check_workspace_request_ownership(workspace_request, user):
    """Verify the user is the requestor of the workspace request, or raise 403."""
    if workspace_request.requestor and hasattr(workspace_request.requestor, 'id'):
        requestor_id = workspace_request.requestor.id
    elif isinstance(workspace_request.requestor, dict):
        requestor_id = workspace_request.requestor.get('id')
    else:
        requestor_id = None

    if requestor_id and requestor_id != user.id:
        raise HTTPException(
            status_code=status_code.HTTP_403_FORBIDDEN,
            detail=strings.WORKSPACE_REQUEST_UNAUTHORIZED
        )


@workspace_requests_core_router.post("/workspace-requests", status_code=status_code.HTTP_201_CREATED,
                                     response_model=WorkspaceRequestWithAllowedUserActions, name=strings.API_CREATE_WORKSPACE_REQUEST,
                                     dependencies=[Depends(get_current_tre_user)])
async def create_workspace_request_draft(workspace_request_input: WorkspaceRequestInCreate,
                                         user=Depends(get_current_tre_user),
                                         workspace_request_repo=Depends(get_repository(WorkspaceRequestRepository))) -> WorkspaceRequestWithAllowedUserActions:
    try:
        workspace_request = workspace_request_repo.create_workspace_request_item(workspace_request_input, user)
        await save_workspace_request(workspace_request, workspace_request_repo, user)
        allowed_actions = get_allowed_actions(workspace_request, user, workspace_request_repo)
        return WorkspaceRequestWithAllowedUserActions(workspaceRequest=workspace_request, allowedUserActions=allowed_actions)
    except (ValidationError, ValueError) as e:
        logger.exception("Failed creating workspace request model instance")
        raise HTTPException(status_code=status_code.HTTP_400_BAD_REQUEST, detail=str(e))


@workspace_requests_core_router.get("/workspace-requests",
                                    status_code=status_code.HTTP_200_OK,
                                    response_model=WorkspaceRequestWithAllowedUserActionsInList,
                                    name=strings.API_LIST_WORKSPACE_REQUESTS,
                                    dependencies=[Depends(get_current_tre_user_or_tre_admin)])
async def get_workspace_requests(workspace_request_repo=Depends(get_repository(WorkspaceRequestRepository)),
                                 user=Depends(get_current_tre_user_or_tre_admin),
                                 status: Optional[WorkspaceRequestStatus] = None,
                                 order_by: Optional[str] = None,
                                 order_ascending: bool = True) -> WorkspaceRequestWithAllowedUserActionsInList:
    try:
        requestor_id = None
        if "TREAdmin" not in user.roles:
            requestor_id = user.id

        workspace_requests = await workspace_request_repo.get_workspace_requests(
            requestor_id=requestor_id, status=status,
            order_by=order_by, order_ascending=order_ascending)
        enriched = enrich_requests_with_allowed_actions(workspace_requests, user, workspace_request_repo)
        return WorkspaceRequestWithAllowedUserActionsInList(workspaceRequests=enriched)
    except (ValidationError, ValueError) as e:
        logger.exception("Failed retrieving workspace requests")
        raise HTTPException(status_code=status_code.HTTP_400_BAD_REQUEST, detail=str(e))


@workspace_requests_core_router.get("/workspace-requests/{workspace_request_id}", status_code=status_code.HTTP_200_OK,
                                    response_model=WorkspaceRequestWithAllowedUserActions, name=strings.API_GET_WORKSPACE_REQUEST,
                                    dependencies=[Depends(get_current_tre_user_or_tre_admin)])
async def retrieve_workspace_request_by_id(workspace_request=Depends(get_workspace_request_by_id_from_path),
                                           workspace_request_repo=Depends(get_repository(WorkspaceRequestRepository)),
                                           user=Depends(get_current_tre_user_or_tre_admin)) -> WorkspaceRequestWithAllowedUserActions:
    # Non-admin users can only view their own requests
    if "TREAdmin" not in user.roles:
        _check_workspace_request_ownership(workspace_request, user)
    allowed_actions = get_allowed_actions(workspace_request, user, workspace_request_repo)
    return WorkspaceRequestWithAllowedUserActions(workspaceRequest=workspace_request, allowedUserActions=allowed_actions)


@workspace_requests_core_router.post("/workspace-requests/{workspace_request_id}/submit", status_code=status_code.HTTP_200_OK,
                                     response_model=WorkspaceRequestWithAllowedUserActions, name=strings.API_SUBMIT_WORKSPACE_REQUEST,
                                     dependencies=[Depends(get_current_tre_user)])
async def submit_workspace_request(workspace_request=Depends(get_workspace_request_by_id_from_path),
                                   user=Depends(get_current_tre_user),
                                   workspace_request_repo=Depends(get_repository(WorkspaceRequestRepository))) -> WorkspaceRequestWithAllowedUserActions:
    # Only the original requestor can submit their request
    _check_workspace_request_ownership(workspace_request, user)
    updated_request = await update_workspace_request(workspace_request, workspace_request_repo, user,
                                                     new_status=WorkspaceRequestStatus.Submitted)
    allowed_actions = get_allowed_actions(updated_request, user, workspace_request_repo)
    return WorkspaceRequestWithAllowedUserActions(workspaceRequest=updated_request, allowedUserActions=allowed_actions)


@workspace_requests_core_router.post("/workspace-requests/{workspace_request_id}/cancel", status_code=status_code.HTTP_200_OK,
                                     response_model=WorkspaceRequestWithAllowedUserActions, name=strings.API_CANCEL_WORKSPACE_REQUEST,
                                     dependencies=[Depends(get_current_tre_user)])
async def cancel_workspace_request(workspace_request=Depends(get_workspace_request_by_id_from_path),
                                   user=Depends(get_current_tre_user),
                                   workspace_request_repo=Depends(get_repository(WorkspaceRequestRepository))) -> WorkspaceRequestWithAllowedUserActions:
    # Only the original requestor can cancel their request
    _check_workspace_request_ownership(workspace_request, user)
    updated_request = await update_workspace_request(workspace_request, workspace_request_repo, user,
                                                     new_status=WorkspaceRequestStatus.Cancelled)
    allowed_actions = get_allowed_actions(updated_request, user, workspace_request_repo)
    return WorkspaceRequestWithAllowedUserActions(workspaceRequest=updated_request, allowedUserActions=allowed_actions)


@workspace_requests_core_router.post("/workspace-requests/{workspace_request_id}/review",
                                     status_code=status_code.HTTP_200_OK,
                                     response_model=WorkspaceRequestWithAllowedUserActions,
                                     name=strings.API_REVIEW_WORKSPACE_REQUEST,
                                     dependencies=[Depends(get_current_admin_user)])
async def review_workspace_request(review_input: WorkspaceRequestReviewInCreate,
                                   workspace_request=Depends(get_workspace_request_by_id_from_path),
                                   user=Depends(get_current_admin_user),
                                   workspace_request_repo=Depends(get_repository(WorkspaceRequestRepository))) -> WorkspaceRequestWithAllowedUserActions:
    try:
        updated_request = await review_workspace_request_service(review_input, workspace_request, user, workspace_request_repo)
        allowed_actions = get_allowed_actions(updated_request, user, workspace_request_repo)
        return WorkspaceRequestWithAllowedUserActions(workspaceRequest=updated_request, allowedUserActions=allowed_actions)
    except (ValidationError, ValueError) as e:
        logger.exception("Failed creating workspace request review model instance")
        raise HTTPException(status_code=status_code.HTTP_400_BAD_REQUEST, detail=str(e))
