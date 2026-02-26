import pytest
from unittest.mock import AsyncMock, MagicMock
from mock import patch

from models.domain.workspace_request import WorkspaceRequest, WorkspaceRequestStatus, WorkspaceRequestActions
from models.domain.authentication import User
from models.schemas.workspace_request import WorkspaceRequestReviewInCreate
from services.workspace_requests import (
    get_allowed_actions, review_workspace_request, enrich_requests_with_allowed_actions
)
from db.repositories.workspace_requests import WorkspaceRequestRepository
from tests_ma.test_api.conftest import create_test_user, create_admin_user, create_non_admin_user

pytestmark = pytest.mark.asyncio

WORKSPACE_REQUEST_ID = "af89dccd-cdf8-4e47-8cfe-995faeac0f09"


def sample_workspace_request(status=WorkspaceRequestStatus.Draft, request_id=WORKSPACE_REQUEST_ID):
    return WorkspaceRequest(
        id=request_id,
        title="Test Workspace",
        businessJustification="test justification",
        workspaceType="tre-workspace-base",
        status=status,
        reviews=[]
    )


async def test_tre_user_can_submit_draft_request():
    repo = MagicMock(spec=WorkspaceRequestRepository)
    repo.validate_status_update = WorkspaceRequestRepository.validate_status_update.__get__(repo, WorkspaceRequestRepository)
    user = create_non_admin_user()

    request = sample_workspace_request(status=WorkspaceRequestStatus.Draft)
    actions = get_allowed_actions(request, user, repo)

    assert WorkspaceRequestActions.Submit in actions
    assert WorkspaceRequestActions.Cancel in actions
    assert WorkspaceRequestActions.Review not in actions


async def test_tre_admin_can_review_in_review_request():
    repo = MagicMock(spec=WorkspaceRequestRepository)
    repo.validate_status_update = WorkspaceRequestRepository.validate_status_update.__get__(repo, WorkspaceRequestRepository)
    user = create_admin_user()

    request = sample_workspace_request(status=WorkspaceRequestStatus.InReview)
    actions = get_allowed_actions(request, user, repo)

    assert WorkspaceRequestActions.Review in actions


async def test_no_actions_for_approved_request():
    repo = MagicMock(spec=WorkspaceRequestRepository)
    repo.validate_status_update = WorkspaceRequestRepository.validate_status_update.__get__(repo, WorkspaceRequestRepository)
    user = create_admin_user()

    request = sample_workspace_request(status=WorkspaceRequestStatus.Approved)
    actions = get_allowed_actions(request, user, repo)

    assert len(actions) == 0


async def test_no_actions_for_rejected_request():
    repo = MagicMock(spec=WorkspaceRequestRepository)
    repo.validate_status_update = WorkspaceRequestRepository.validate_status_update.__get__(repo, WorkspaceRequestRepository)
    user = create_admin_user()

    request = sample_workspace_request(status=WorkspaceRequestStatus.Rejected)
    actions = get_allowed_actions(request, user, repo)

    assert len(actions) == 0


async def test_enriches_multiple_requests():
    repo = MagicMock(spec=WorkspaceRequestRepository)
    repo.validate_status_update = WorkspaceRequestRepository.validate_status_update.__get__(repo, WorkspaceRequestRepository)
    user = create_non_admin_user()

    requests = [
        sample_workspace_request(status=WorkspaceRequestStatus.Draft),
        sample_workspace_request(status=WorkspaceRequestStatus.Submitted)
    ]
    enriched = enrich_requests_with_allowed_actions(requests, user, repo)

    assert len(enriched) == 2
    assert enriched[0].workspaceRequest.status == WorkspaceRequestStatus.Draft
    assert enriched[1].workspaceRequest.status == WorkspaceRequestStatus.Submitted


async def test_review_approves_request():
    repo = MagicMock(spec=WorkspaceRequestRepository)
    repo.validate_status_update = WorkspaceRequestRepository.validate_status_update.__get__(repo, WorkspaceRequestRepository)

    review_input = WorkspaceRequestReviewInCreate(approval=True, decisionExplanation="Approved")
    user = create_admin_user()
    request = sample_workspace_request(status=WorkspaceRequestStatus.InReview)

    approved_request = sample_workspace_request(status=WorkspaceRequestStatus.Approved)
    repo.update_workspace_request = AsyncMock(return_value=approved_request)
    repo.create_workspace_request_review_item = MagicMock()
    review_mock = MagicMock()
    review_mock.reviewDecision = "approved"
    repo.create_workspace_request_review_item.return_value = review_mock

    result = await review_workspace_request(review_input, request, user, repo)

    assert result.status == WorkspaceRequestStatus.Approved


async def test_review_rejects_request():
    repo = MagicMock(spec=WorkspaceRequestRepository)
    repo.validate_status_update = WorkspaceRequestRepository.validate_status_update.__get__(repo, WorkspaceRequestRepository)

    review_input = WorkspaceRequestReviewInCreate(approval=False, decisionExplanation="Not needed")
    user = create_admin_user()
    request = sample_workspace_request(status=WorkspaceRequestStatus.InReview)

    rejected_request = sample_workspace_request(status=WorkspaceRequestStatus.Rejected)
    repo.update_workspace_request = AsyncMock(return_value=rejected_request)
    repo.create_workspace_request_review_item = MagicMock()
    review_mock = MagicMock()
    review_mock.reviewDecision = "rejected"
    repo.create_workspace_request_review_item.return_value = review_mock

    result = await review_workspace_request(review_input, request, user, repo)

    assert result.status == WorkspaceRequestStatus.Rejected
