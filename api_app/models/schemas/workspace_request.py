import uuid
from datetime import datetime, timezone
from typing import List
from pydantic import BaseModel, Field
from models.domain.workspace_request import WorkspaceRequest, WorkspaceRequestActions


def get_sample_workspace_request_review(review_id: str) -> dict:
    return {
        "reviewId": review_id,
        "reviewDecision": "approved",
        "decisionExplanation": "Describe why the request was approved/rejected"
    }


def get_sample_workspace_request(request_id: str) -> dict:
    return {
        "requestId": request_id,
        "status": "draft",
        "title": "New research workspace",
        "businessJustification": "Need a workspace for genomics research",
        "workspaceType": "tre-workspace-base",
        "properties": {},
        "requestor": {
            "id": "a user id",
            "name": "a user name"
        },
        "createdWhen": datetime.now(timezone.utc).timestamp(),
        "reviews": []
    }


def get_sample_workspace_request_with_allowed_user_actions() -> dict:
    return {
        "workspaceRequest": get_sample_workspace_request(str(uuid.uuid4())),
        "allowedUserActions": [WorkspaceRequestActions.Cancel, WorkspaceRequestActions.Submit],
    }


class WorkspaceRequestWithAllowedUserActions(BaseModel):
    workspaceRequest: WorkspaceRequest = Field(title="Workspace Request")
    allowedUserActions: List[str] = Field([], title="Actions that the requesting user can do on the request")

    class Config:
        schema_extra = {
            "example": get_sample_workspace_request_with_allowed_user_actions(),
        }


class WorkspaceRequestWithAllowedUserActionsInList(BaseModel):
    workspaceRequests: List[WorkspaceRequestWithAllowedUserActions] = Field([], title="Workspace Requests")

    class Config:
        schema_extra = {
            "example": {
                "workspaceRequests": [
                    get_sample_workspace_request_with_allowed_user_actions(),
                    get_sample_workspace_request_with_allowed_user_actions()
                ]
            }
        }


class WorkspaceRequestInCreate(BaseModel):
    title: str = Field("Workspace Request", title="Brief title for the request")
    businessJustification: str = Field("", title="Explanation that will be provided to the request reviewer")
    workspaceType: str = Field("", title="Workspace template name")
    properties: dict = Field({}, title="Workspace parameters from the template JSON schema")

    class Config:
        schema_extra = {
            "example": {
                "title": "New research workspace",
                "businessJustification": "Need a workspace for genomics research",
                "workspaceType": "tre-workspace-base",
                "properties": {}
            }
        }


class WorkspaceRequestReviewInCreate(BaseModel):
    approval: bool = Field(title="Workspace request review decision")
    decisionExplanation: str = Field("Decision Explanation", title="Explanation of the reviewer for the review decision")

    class Config:
        schema_extra = {
            "example": {
                "approval": True,
                "decisionExplanation": "the reason why this request was approved/rejected"
            }
        }
