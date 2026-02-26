from enum import StrEnum
from typing import List, Optional

from models.domain.azuretremodel import AzureTREModel
from pydantic import Field, validator
from resources import strings


class WorkspaceRequestStatus(StrEnum):
    Draft = strings.WORKSPACE_REQUEST_STATUS_DRAFT
    Submitted = strings.WORKSPACE_REQUEST_STATUS_SUBMITTED
    InReview = strings.WORKSPACE_REQUEST_STATUS_INREVIEW
    Approved = strings.WORKSPACE_REQUEST_STATUS_APPROVED
    Rejected = strings.WORKSPACE_REQUEST_STATUS_REJECTED
    Cancelled = strings.WORKSPACE_REQUEST_STATUS_CANCELLED


class WorkspaceRequestActions(StrEnum):
    Submit = strings.WORKSPACE_REQUEST_ACTION_SUBMIT
    Cancel = strings.WORKSPACE_REQUEST_ACTION_CANCEL
    Review = strings.WORKSPACE_REQUEST_ACTION_REVIEW


class WorkspaceRequestReviewDecision(StrEnum):
    Approved = strings.WORKSPACE_REQUEST_REVIEW_DECISION_APPROVED
    Rejected = strings.WORKSPACE_REQUEST_REVIEW_DECISION_REJECTED


class WorkspaceRequestReview(AzureTREModel):
    id: str = Field(title="Id", description="GUID identifying the review")
    reviewer: dict = {}
    dateCreated: float = 0
    reviewDecision: WorkspaceRequestReviewDecision = Field("", title="Workspace request review decision")
    decisionExplanation: str = Field("", title="Explanation why the request was approved/rejected")


class WorkspaceRequestHistoryItem(AzureTREModel):
    resourceVersion: int
    updatedWhen: float
    updatedBy: dict = {}
    properties: dict = {}


class WorkspaceRequest(AzureTREModel):
    id: str = Field(title="Id", description="GUID identifying the workspace request")
    resourceType: str = "workspace_request"
    resourceVersion: int = 0
    requestor: dict = {}
    createdWhen: float = Field(None, title="Creation time of the request")
    updatedBy: dict = {}
    updatedWhen: float = 0
    history: List[WorkspaceRequestHistoryItem] = []
    title: str = Field("Workspace Request", title="Brief title for the request")
    businessJustification: str = Field("", title="Explanation that will be provided to the request reviewer")
    workspaceType: str = Field("", title="Workspace template name")
    properties: dict = Field({}, title="Workspace parameters from the template JSON schema")
    status: WorkspaceRequestStatus = WorkspaceRequestStatus.Draft
    reviews: Optional[List[WorkspaceRequestReview]]
    etag: Optional[str] = Field(title="_etag", alias="_etag")

    @validator("etag", pre=True)
    def parse_etag_to_remove_escaped_quotes(cls, value):
        if value:
            return value.replace('\"', '')
