from unittest.mock import AsyncMock
from fastapi import HTTPException
from mock import patch
import pytest
import pytest_asyncio
from models.domain.authentication import User
from tests_ma.test_api.conftest import create_test_user
from models.schemas.workspace_request import WorkspaceRequestInCreate, WorkspaceRequestReviewInCreate
from models.domain.workspace_request import WorkspaceRequest, WorkspaceRequestStatus
from db.repositories.workspace_requests import WorkspaceRequestRepository

from azure.cosmos.exceptions import CosmosResourceNotFoundError, CosmosAccessConditionFailedError

pytestmark = pytest.mark.asyncio

WORKSPACE_REQUEST_ID = "ce45d43a-e734-469a-88a0-109faf4a611f"
DRAFT = WorkspaceRequestStatus.Draft
SUBMITTED = WorkspaceRequestStatus.Submitted
IN_REVIEW = WorkspaceRequestStatus.InReview
APPROVED = WorkspaceRequestStatus.Approved
REJECTED = WorkspaceRequestStatus.Rejected
CANCELLED = WorkspaceRequestStatus.Cancelled

ALL_STATUSES = [enum.value for enum in WorkspaceRequestStatus]

ALLOWED_STATUS_CHANGES = {
    DRAFT: [SUBMITTED, CANCELLED],
    SUBMITTED: [IN_REVIEW, CANCELLED],
    IN_REVIEW: [APPROVED, REJECTED],
    APPROVED: [],
    REJECTED: [],
    CANCELLED: [],
}


@pytest_asyncio.fixture
async def workspace_request_repo():
    with patch('api.dependencies.database.Database.get_container_proxy', return_value=AsyncMock()):
        repo = await WorkspaceRequestRepository.create()
        yield repo


@pytest.fixture
def sample_workspace_request_input():
    return WorkspaceRequestInCreate(
        title="Test Workspace",
        businessJustification="Some business justification",
        workspaceType="tre-workspace-base",
        properties={}
    )


@pytest.fixture
def verify_dictionary_contains_all_enum_values():
    for status in ALL_STATUSES:
        if status not in ALLOWED_STATUS_CHANGES:
            raise Exception(f"Status '{status}' was not added to the ALLOWED_STATUS_CHANGES dictionary")


async def test_create_workspace_request_item_creates_request_with_correct_values(workspace_request_repo, sample_workspace_request_input):
    user = create_test_user()
    workspace_request = workspace_request_repo.create_workspace_request_item(sample_workspace_request_input, user)

    assert workspace_request.title == "Test Workspace"
    assert workspace_request.businessJustification == "Some business justification"
    assert workspace_request.workspaceType == "tre-workspace-base"
    assert workspace_request.status == WorkspaceRequestStatus.Draft
    assert workspace_request.requestor == user
    assert workspace_request.reviews == []


@pytest.mark.parametrize("current_status", ALL_STATUSES)
async def test_all_status_transitions_are_covered(current_status, workspace_request_repo, verify_dictionary_contains_all_enum_values):
    for new_status in ALL_STATUSES:
        expected = new_status in [s.value if hasattr(s, 'value') else s for s in ALLOWED_STATUS_CHANGES.get(current_status, [])]
        result = workspace_request_repo.validate_status_update(current_status, new_status)
        assert result == expected, f"Transition from {current_status} to {new_status}: expected {expected}, got {result}"


async def test_get_workspace_request_by_id_raises_entity_does_not_exist_if_item_not_found(workspace_request_repo):
    workspace_request_repo.read_item_by_id = AsyncMock(side_effect=CosmosResourceNotFoundError)

    from db.errors import EntityDoesNotExist
    with pytest.raises(EntityDoesNotExist):
        await workspace_request_repo.get_workspace_request_by_id(WORKSPACE_REQUEST_ID)


async def test_get_workspace_requests_queries_with_no_filters(workspace_request_repo):
    workspace_request_repo.query = AsyncMock(return_value=[])
    result = await workspace_request_repo.get_workspace_requests()

    workspace_request_repo.query.assert_called_once_with(query='SELECT * FROM c', parameters=[])
    assert result == []


async def test_get_workspace_requests_queries_with_requestor_filter(workspace_request_repo):
    workspace_request_repo.query = AsyncMock(return_value=[])
    await workspace_request_repo.get_workspace_requests(requestor_id="user-123")

    workspace_request_repo.query.assert_called_once_with(
        query='SELECT * FROM c WHERE c.requestor.id=@requestor_id',
        parameters=[{"name": "@requestor_id", "value": "user-123"}]
    )


async def test_get_workspace_requests_queries_with_status_filter(workspace_request_repo):
    workspace_request_repo.query = AsyncMock(return_value=[])
    await workspace_request_repo.get_workspace_requests(status=WorkspaceRequestStatus.Draft)

    workspace_request_repo.query.assert_called_once_with(
        query='SELECT * FROM c WHERE c.status=@status',
        parameters=[{"name": "@status", "value": "draft"}]
    )


async def test_get_workspace_requests_queries_with_order_by(workspace_request_repo):
    workspace_request_repo.query = AsyncMock(return_value=[])
    await workspace_request_repo.get_workspace_requests(order_by="createdWhen", order_ascending=False)

    workspace_request_repo.query.assert_called_once_with(
        query='SELECT * FROM c ORDER BY c.createdWhen DESC',
        parameters=[]
    )


async def test_create_review_item_approved(workspace_request_repo):
    review_input = WorkspaceRequestReviewInCreate(approval=True, decisionExplanation="Looks good")
    user = create_test_user()

    review = workspace_request_repo.create_workspace_request_review_item(review_input, user)

    assert review.reviewDecision == "approved"
    assert review.decisionExplanation == "Looks good"
    assert review.reviewer == user


async def test_create_review_item_rejected(workspace_request_repo):
    review_input = WorkspaceRequestReviewInCreate(approval=False, decisionExplanation="Not needed")
    user = create_test_user()

    review = workspace_request_repo.create_workspace_request_review_item(review_input, user)

    assert review.reviewDecision == "rejected"
    assert review.decisionExplanation == "Not needed"
