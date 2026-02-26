from fastapi import HTTPException, status
from services.logging import logger

from models.domain.workspace_request import (
    WorkspaceRequest, WorkspaceRequestStatus,
    WorkspaceRequestActions, WorkspaceRequestReviewDecision
)
from models.domain.authentication import User
from models.schemas.workspace_request import (
    WorkspaceRequestReviewInCreate,
    WorkspaceRequestWithAllowedUserActions
)
from typing import List, Optional
from db.repositories.workspace_requests import WorkspaceRequestRepository
from resources import strings


async def save_workspace_request(workspace_request: WorkspaceRequest, workspace_request_repo: WorkspaceRequestRepository, user: User):
    try:
        logger.debug(f"Saving workspace request item: {workspace_request.id}")
        workspace_request.updatedBy = user
        await workspace_request_repo.save_item(workspace_request)
    except Exception:
        logger.exception(f'Failed saving workspace request {workspace_request}')
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=strings.STATE_STORE_ENDPOINT_NOT_RESPONDING)


async def update_workspace_request(
        workspace_request: WorkspaceRequest,
        workspace_request_repo: WorkspaceRequestRepository,
        updated_by: User,
        new_status: Optional[WorkspaceRequestStatus] = None,
        workspace_request_review=None) -> WorkspaceRequest:
    try:
        logger.debug(f"Updating workspace request item: {workspace_request.id}")
        updated_request = await workspace_request_repo.update_workspace_request(
            original_request=workspace_request,
            updated_by=updated_by,
            new_status=new_status,
            workspace_request_review=workspace_request_review)
    except Exception as e:
        logger.exception(f'Failed updating workspace request item {workspace_request}')
        if hasattr(e, 'status_code'):
            if e.status_code == 400:  # type: ignore
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=strings.WORKSPACE_REQUEST_ILLEGAL_STATUS_CHANGE)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=strings.STATE_STORE_ENDPOINT_NOT_RESPONDING)

    return updated_request


async def review_workspace_request(review_input: WorkspaceRequestReviewInCreate, workspace_request: WorkspaceRequest, user: User,
                                   workspace_request_repo: WorkspaceRequestRepository) -> WorkspaceRequest:
    review = workspace_request_repo.create_workspace_request_review_item(review_input, user)

    if review.reviewDecision == WorkspaceRequestReviewDecision.Approved:
        review_status = WorkspaceRequestStatus.Approved
    else:
        review_status = WorkspaceRequestStatus.Rejected

    updated_request = await update_workspace_request(
        workspace_request=workspace_request,
        workspace_request_repo=workspace_request_repo,
        updated_by=user,
        new_status=review_status,
        workspace_request_review=review)

    return updated_request


def get_allowed_actions(request: WorkspaceRequest, user: User, workspace_request_repo: WorkspaceRequestRepository) -> List[str]:
    allowed_actions = []

    can_review_request = workspace_request_repo.validate_status_update(request.status, WorkspaceRequestStatus.Approved)
    can_cancel_request = workspace_request_repo.validate_status_update(request.status, WorkspaceRequestStatus.Cancelled)
    can_submit_request = workspace_request_repo.validate_status_update(request.status, WorkspaceRequestStatus.Submitted)

    if can_review_request and "TREAdmin" in user.roles:
        allowed_actions.append(WorkspaceRequestActions.Review)

    if can_cancel_request and "TREUser" in user.roles:
        allowed_actions.append(WorkspaceRequestActions.Cancel)

    if can_submit_request and "TREUser" in user.roles:
        allowed_actions.append(WorkspaceRequestActions.Submit)

    return allowed_actions


def enrich_requests_with_allowed_actions(requests: List[WorkspaceRequest], user: User,
                                         workspace_request_repo: WorkspaceRequestRepository) -> List[WorkspaceRequestWithAllowedUserActions]:
    enriched_requests = []
    for request in requests:
        allowed_actions = get_allowed_actions(request, user, workspace_request_repo)
        enriched_requests.append(WorkspaceRequestWithAllowedUserActions(workspaceRequest=request, allowedUserActions=allowed_actions))
    return enriched_requests
