import pytest
import pytest_asyncio
from mock import patch
from fastapi import status

from tests_ma.test_api.conftest import create_test_user, create_admin_user, create_non_admin_user
from models.domain.workspace_request import WorkspaceRequest, WorkspaceRequestStatus, WorkspaceRequestReview, WorkspaceRequestReviewDecision
from resources import strings
from services.authentication import get_current_tre_user_or_tre_admin, get_current_admin_user, get_current_tre_user

pytestmark = pytest.mark.asyncio

WORKSPACE_REQUEST_ID = "af89dccd-cdf8-4e47-8cfe-995faeac0f09"


def sample_workspace_request(status=WorkspaceRequestStatus.Draft, request_id=WORKSPACE_REQUEST_ID, requestor=None):
    if requestor is None:
        requestor = create_non_admin_user()
    return WorkspaceRequest(
        id=request_id,
        title="Test Workspace",
        businessJustification="test justification",
        workspaceType="tre-workspace-base",
        status=status,
        requestor=requestor,
        reviews=[]
    )


class TestWorkspaceRequestRoutesForTREUser:
    @pytest_asyncio.fixture(autouse=True, scope='class')
    def log_in_with_tre_user(self, app):
        user = create_non_admin_user()
        app.dependency_overrides[get_current_tre_user] = lambda: user
        app.dependency_overrides[get_current_tre_user_or_tre_admin] = lambda: user
        yield
        app.dependency_overrides = {}

    # [POST] /workspace-requests
    @patch("api.routes.workspace_requests.WorkspaceRequestRepository.create_workspace_request_item", return_value=sample_workspace_request())
    @patch("api.routes.workspace_requests.save_workspace_request")
    async def test_post_workspace_request_creates_draft_returns_201(self, _, __, app, client):
        input_data = {
            "title": "New Workspace",
            "businessJustification": "Need workspace for research",
            "workspaceType": "tre-workspace-base"
        }
        response = await client.post(app.url_path_for(strings.API_CREATE_WORKSPACE_REQUEST), json=input_data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["workspaceRequest"]["id"] == WORKSPACE_REQUEST_ID

    @patch("api.routes.workspace_requests.WorkspaceRequestRepository.create_workspace_request_item", side_effect=ValueError)
    async def test_post_workspace_request_malformed_input_returns_400(self, _, app, client):
        input_data = {
            "title": "New Workspace",
            "businessJustification": "justification",
            "workspaceType": "tre-workspace-base"
        }
        response = await client.post(app.url_path_for(strings.API_CREATE_WORKSPACE_REQUEST), json=input_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # [GET] /workspace-requests
    @patch("api.routes.workspace_requests.WorkspaceRequestRepository.get_workspace_requests", return_value=[])
    async def test_get_workspace_requests_returns_200(self, _, app, client):
        response = await client.get(app.url_path_for(strings.API_LIST_WORKSPACE_REQUESTS))
        assert response.status_code == status.HTTP_200_OK

    # [GET] /workspace-requests/{workspace_request_id}
    @patch("api.routes.workspace_requests.WorkspaceRequestRepository.read_item_by_id", return_value=sample_workspace_request())
    async def test_get_workspace_request_by_id_returns_200(self, _, app, client):
        response = await client.get(app.url_path_for(strings.API_GET_WORKSPACE_REQUEST, workspace_request_id=WORKSPACE_REQUEST_ID))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["workspaceRequest"]["id"] == WORKSPACE_REQUEST_ID

    # [GET] /workspace-requests/{workspace_request_id} - other user's request returns 403
    @patch("api.routes.workspace_requests.WorkspaceRequestRepository.read_item_by_id")
    async def test_get_other_users_workspace_request_returns_403(self, mock_read, app, client):
        other_user = create_test_user()
        other_user.id = "other-user-id"
        mock_read.return_value = sample_workspace_request(requestor=other_user)
        response = await client.get(app.url_path_for(strings.API_GET_WORKSPACE_REQUEST, workspace_request_id=WORKSPACE_REQUEST_ID))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # [POST] /workspace-requests/{workspace_request_id}/submit
    @patch("api.routes.workspace_requests.WorkspaceRequestRepository.read_item_by_id", return_value=sample_workspace_request())
    @patch("api.routes.workspace_requests.update_workspace_request", return_value=sample_workspace_request(status=WorkspaceRequestStatus.Submitted))
    async def test_submit_workspace_request_returns_200(self, _, __, app, client):
        response = await client.post(app.url_path_for(strings.API_SUBMIT_WORKSPACE_REQUEST, workspace_request_id=WORKSPACE_REQUEST_ID))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["workspaceRequest"]["status"] == WorkspaceRequestStatus.Submitted

    # [POST] /workspace-requests/{workspace_request_id}/submit - other user's request returns 403
    @patch("api.routes.workspace_requests.WorkspaceRequestRepository.read_item_by_id")
    async def test_submit_other_users_workspace_request_returns_403(self, mock_read, app, client):
        other_user = create_test_user()
        other_user.id = "other-user-id"
        mock_read.return_value = sample_workspace_request(requestor=other_user)
        response = await client.post(app.url_path_for(strings.API_SUBMIT_WORKSPACE_REQUEST, workspace_request_id=WORKSPACE_REQUEST_ID))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # [POST] /workspace-requests/{workspace_request_id}/cancel
    @patch("api.routes.workspace_requests.WorkspaceRequestRepository.read_item_by_id", return_value=sample_workspace_request())
    @patch("api.routes.workspace_requests.update_workspace_request", return_value=sample_workspace_request(status=WorkspaceRequestStatus.Cancelled))
    async def test_cancel_workspace_request_returns_200(self, _, __, app, client):
        response = await client.post(app.url_path_for(strings.API_CANCEL_WORKSPACE_REQUEST, workspace_request_id=WORKSPACE_REQUEST_ID))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["workspaceRequest"]["status"] == WorkspaceRequestStatus.Cancelled

    # [POST] /workspace-requests/{workspace_request_id}/cancel - other user's request returns 403
    @patch("api.routes.workspace_requests.WorkspaceRequestRepository.read_item_by_id")
    async def test_cancel_other_users_workspace_request_returns_403(self, mock_read, app, client):
        other_user = create_test_user()
        other_user.id = "other-user-id"
        mock_read.return_value = sample_workspace_request(requestor=other_user)
        response = await client.post(app.url_path_for(strings.API_CANCEL_WORKSPACE_REQUEST, workspace_request_id=WORKSPACE_REQUEST_ID))
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestWorkspaceRequestRoutesForTREAdmin:
    @pytest_asyncio.fixture(autouse=True, scope='class')
    def log_in_with_admin_user(self, app):
        user = create_admin_user()
        app.dependency_overrides[get_current_admin_user] = lambda: user
        app.dependency_overrides[get_current_tre_user_or_tre_admin] = lambda: user
        yield
        app.dependency_overrides = {}

    # [GET] /workspace-requests (admin sees all)
    @patch("api.routes.workspace_requests.WorkspaceRequestRepository.get_workspace_requests", return_value=[])
    async def test_get_workspace_requests_as_admin_returns_200(self, _, app, client):
        response = await client.get(app.url_path_for(strings.API_LIST_WORKSPACE_REQUESTS))
        assert response.status_code == status.HTTP_200_OK

    # [POST] /workspace-requests/{workspace_request_id}/review (from InReview)
    @patch("api.routes.workspace_requests.WorkspaceRequestRepository.read_item_by_id", return_value=sample_workspace_request(status=WorkspaceRequestStatus.InReview))
    @patch("api.routes.workspace_requests.review_workspace_request_service", return_value=sample_workspace_request(status=WorkspaceRequestStatus.Approved))
    async def test_review_approve_workspace_request_returns_200(self, _, __, app, client):
        review_input = {"approval": True, "decisionExplanation": "Looks good"}
        response = await client.post(
            app.url_path_for(strings.API_REVIEW_WORKSPACE_REQUEST, workspace_request_id=WORKSPACE_REQUEST_ID),
            json=review_input)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["workspaceRequest"]["status"] == WorkspaceRequestStatus.Approved

    @patch("api.routes.workspace_requests.WorkspaceRequestRepository.read_item_by_id", return_value=sample_workspace_request(status=WorkspaceRequestStatus.InReview))
    @patch("api.routes.workspace_requests.review_workspace_request_service", return_value=sample_workspace_request(status=WorkspaceRequestStatus.Rejected))
    async def test_review_reject_workspace_request_returns_200(self, _, __, app, client):
        review_input = {"approval": False, "decisionExplanation": "Not needed"}
        response = await client.post(
            app.url_path_for(strings.API_REVIEW_WORKSPACE_REQUEST, workspace_request_id=WORKSPACE_REQUEST_ID),
            json=review_input)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["workspaceRequest"]["status"] == WorkspaceRequestStatus.Rejected

    # [POST] /workspace-requests/{workspace_request_id}/review (from Submitted - auto-transitions via InReview)
    @patch("api.routes.workspace_requests.WorkspaceRequestRepository.read_item_by_id", return_value=sample_workspace_request(status=WorkspaceRequestStatus.Submitted))
    @patch("api.routes.workspace_requests.review_workspace_request_service", return_value=sample_workspace_request(status=WorkspaceRequestStatus.Approved))
    async def test_review_submitted_request_auto_transitions_and_approves(self, _, __, app, client):
        review_input = {"approval": True, "decisionExplanation": "Approved from submitted"}
        response = await client.post(
            app.url_path_for(strings.API_REVIEW_WORKSPACE_REQUEST, workspace_request_id=WORKSPACE_REQUEST_ID),
            json=review_input)
        assert response.status_code == status.HTTP_200_OK
