import copy
import uuid

from datetime import datetime, UTC
from typing import List, Optional
from pydantic import UUID4
from azure.cosmos.exceptions import CosmosResourceNotFoundError, CosmosAccessConditionFailedError
from fastapi import HTTPException, status
from pydantic import parse_obj_as
from models.domain.authentication import User
from db.errors import EntityDoesNotExist
from models.domain.workspace_request import (
    WorkspaceRequest, WorkspaceRequestStatus,
    WorkspaceRequestReview, WorkspaceRequestReviewDecision,
    WorkspaceRequestHistoryItem
)
from models.schemas.workspace_request import WorkspaceRequestInCreate, WorkspaceRequestReviewInCreate
from core import config
from resources import strings
from db.repositories.base import BaseRepository
from services.logging import logger


class WorkspaceRequestRepository(BaseRepository):
    @classmethod
    async def create(cls):
        cls = WorkspaceRequestRepository()
        await super().create(config.STATE_STORE_WORKSPACE_REQUESTS_CONTAINER)
        return cls

    def get_timestamp(self) -> float:
        return datetime.now(UTC).timestamp()

    async def update_workspace_request_item(self, original_request: WorkspaceRequest, new_request: WorkspaceRequest, updated_by: User, request_properties: dict) -> WorkspaceRequest:
        history_item = WorkspaceRequestHistoryItem(
            resourceVersion=original_request.resourceVersion,
            updatedWhen=original_request.updatedWhen,
            updatedBy=original_request.updatedBy,
            properties=request_properties
        )
        new_request.history.append(history_item)
        new_request.resourceVersion = new_request.resourceVersion + 1
        new_request.updatedBy = updated_by
        new_request.updatedWhen = self.get_timestamp()

        await self.upsert_item_with_etag(new_request, new_request.etag)
        return new_request

    @staticmethod
    def workspace_requests_query():
        return "SELECT * FROM c WHERE c.resourceType = 'workspace_request'"

    def validate_status_update(self, current_status: WorkspaceRequestStatus, new_status: WorkspaceRequestStatus) -> bool:
        valid_transitions = {
            WorkspaceRequestStatus.Draft: {
                WorkspaceRequestStatus.Submitted,
                WorkspaceRequestStatus.Cancelled,
            },
            WorkspaceRequestStatus.Submitted: {
                WorkspaceRequestStatus.InReview,
                WorkspaceRequestStatus.Cancelled,
            },
            WorkspaceRequestStatus.InReview: {
                WorkspaceRequestStatus.Approved,
                WorkspaceRequestStatus.Rejected,
            },
            WorkspaceRequestStatus.Approved: set(),
            WorkspaceRequestStatus.Rejected: set(),
            WorkspaceRequestStatus.Cancelled: set(),
        }

        allowed_transitions = valid_transitions.get(current_status, set())
        return new_status in allowed_transitions

    def create_workspace_request_item(self, workspace_request_input: WorkspaceRequestInCreate, user: User) -> WorkspaceRequest:
        full_request_id = str(uuid.uuid4())

        workspace_request = WorkspaceRequest(
            id=full_request_id,
            title=workspace_request_input.title,
            businessJustification=workspace_request_input.businessJustification,
            workspaceType=workspace_request_input.workspaceType,
            properties=workspace_request_input.properties,
            requestor=user,
            createdWhen=datetime.now(UTC).timestamp(),
            updatedBy=user,
            updatedWhen=datetime.now(UTC).timestamp(),
            reviews=[]
        )

        return workspace_request

    async def get_workspace_requests(self, requestor_id: Optional[str] = None, status: Optional[WorkspaceRequestStatus] = None,
                                     order_by: Optional[str] = None, order_ascending=True) -> List[WorkspaceRequest]:
        query = self.workspace_requests_query()

        conditions = []
        parameters = []
        if requestor_id:
            conditions.append('c.requestor.id=@requestor_id')
            parameters.append({"name": "@requestor_id", "value": requestor_id})
        if status:
            conditions.append('c.status=@status')
            parameters.append({"name": "@status", "value": status})

        if conditions:
            query += ' AND ' + ' AND '.join(conditions)

        if order_by:
            query += ' ORDER BY c.' + order_by
            query += ' ASC' if order_ascending else ' DESC'

        workspace_requests = await self.query(query=query, parameters=parameters)
        return parse_obj_as(List[WorkspaceRequest], workspace_requests)

    async def get_workspace_request_by_id(self, workspace_request_id: UUID4) -> WorkspaceRequest:
        try:
            workspace_request = await self.read_item_by_id(str(workspace_request_id))
        except CosmosResourceNotFoundError:
            raise EntityDoesNotExist
        return parse_obj_as(WorkspaceRequest, workspace_request)

    async def update_workspace_request(
            self,
            original_request: WorkspaceRequest,
            updated_by: User,
            new_status: Optional[WorkspaceRequestStatus] = None,
            workspace_request_review: Optional[WorkspaceRequestReview] = None) -> WorkspaceRequest:
        updated_request = self._build_updated_request(
            original_request=original_request,
            new_status=new_status,
            workspace_request_review=workspace_request_review)
        try:
            db_response = await self.update_workspace_request_item(original_request, updated_request, updated_by, {"previousStatus": original_request.status})
        except CosmosAccessConditionFailedError:
            logger.warning(f"ETag mismatch for workspace request ID: '{original_request.id}'. Retrying.")
            original_request = await self.get_workspace_request_by_id(original_request.id)
            updated_request = self._build_updated_request(original_request=original_request, new_status=new_status, workspace_request_review=workspace_request_review)
            db_response = await self.update_workspace_request_item(original_request, updated_request, updated_by, {"previousStatus": original_request.status})

        return db_response

    def create_workspace_request_review_item(self, review_input: WorkspaceRequestReviewInCreate, reviewer: User) -> WorkspaceRequestReview:
        full_review_id = str(uuid.uuid4())
        review_decision = WorkspaceRequestReviewDecision.Approved if review_input.approval else WorkspaceRequestReviewDecision.Rejected

        review = WorkspaceRequestReview(
            id=full_review_id,
            dateCreated=self.get_timestamp(),
            reviewDecision=review_decision,
            decisionExplanation=review_input.decisionExplanation,
            reviewer=reviewer
        )

        return review

    def _build_updated_request(
            self,
            original_request: WorkspaceRequest,
            new_status: Optional[WorkspaceRequestStatus] = None,
            workspace_request_review: Optional[WorkspaceRequestReview] = None) -> WorkspaceRequest:
        updated_request = copy.deepcopy(original_request)

        if new_status is not None:
            self._validate_status_update(current_status=original_request.status, new_status=new_status)
            updated_request.status = new_status

        if workspace_request_review is not None:
            if updated_request.reviews is None:
                updated_request.reviews = [workspace_request_review]
            else:
                updated_request.reviews.append(workspace_request_review)

        return updated_request

    def _validate_status_update(self, current_status, new_status):
        if not self.validate_status_update(current_status=current_status, new_status=new_status):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=strings.WORKSPACE_REQUEST_ILLEGAL_STATUS_CHANGE)
