from contextlib import asynccontextmanager
from datetime import datetime, time
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional

from pydantic import UUID4

from models.schemas.costs import get_cost_report_responses, get_workspace_cost_report_responses
from core import config
from api.helpers import get_repository
from db.repositories.costs import CostsRepository
from db.repositories.shared_services import SharedServiceRepository
from db.repositories.user_resources import UserResourceRepository
from db.repositories.workspace_services import WorkspaceServiceRepository
from db.repositories.workspaces import WorkspaceRepository
from models.domain.costs import CostIngestRequest, CostReport, GranularityEnum, WorkspaceCostReport
from resources import strings
from services.authentication import get_current_admin_user, get_current_cost_processor, get_current_workspace_owner_or_tre_admin
from services.cost_service import CostService, ServiceUnavailable, SubscriptionNotSupported, TooManyRequests, WorkspaceDoesNotExist, cost_service_factory
from services.logging import logger


costs_core_router = APIRouter(dependencies=[Depends(get_current_admin_user)])
costs_workspace_router = APIRouter(dependencies=[Depends(get_current_workspace_owner_or_tre_admin)])
# Internal, service-to-service router authenticated via the Cost Processor managed identity.
costs_internal_router = APIRouter(dependencies=[Depends(get_current_cost_processor)])


def validate_report_period(from_date: Optional[datetime], to_date: Optional[datetime]):
    if from_date is None and to_date is None:
        # valid option, month to date report
        return

    if from_date is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=strings.API_GET_COSTS_FROM_DATE_REQUIRED)
    if to_date is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=strings.API_GET_COSTS_TO_DATE_REQUIRED)
    if from_date >= to_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=strings.API_GET_COSTS_TO_DATE_NEED_TO_BE_LATER_THEN_FROM_DATE)


@asynccontextmanager
async def cost_query_errors(action: str, internal_error_detail: str = strings.API_GET_COSTS_INTERNAL_SERVER_ERROR):
    """Map the cost service's failure modes onto the API's error responses.

    Shared by every cost endpoint so they stay consistent; the retryable ones carry Retry-After.
    """
    try:
        yield
    except WorkspaceDoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=strings.WORKSPACE_DOES_NOT_EXIST)
    except SubscriptionNotSupported:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=strings.API_GET_COSTS_SUBSCRIPTION_NOT_SUPPORTED)
    except TooManyRequests as e:
        raise RetryableCostError(429, strings.API_GET_COSTS_TOO_MANY_REQUESTS, e.retry_after)
    except ServiceUnavailable as e:
        raise RetryableCostError(503, strings.API_GET_COSTS_SERVICE_UNAVAILABLE, e.retry_after)
    except HTTPException:
        raise
    except Exception:
        logger.exception(action)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=internal_error_detail)


class RetryableCostError(Exception):
    """A throttled/unavailable Cost Management response the caller should retry after a delay."""

    def __init__(self, status_code: int, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.retry_after = retry_after

    def as_response(self) -> JSONResponse:
        return JSONResponse(
            content={"error": {"code": str(self.status_code), "message": self.message,
                               "retry-after": str(self.retry_after)}},
            status_code=self.status_code,
            headers={"Retry-After": str(self.retry_after)})


class CostsQueryParams:
    def __init__(
        self,
        from_date: Optional[datetime] = Query(default=None, description="The start date to pull data from, required if to_date is set, otherwise report will return month to date (iso-8601, UTC)."),
        to_date: Optional[datetime] = Query(default=None, description="The end date to pull data to, required if from_date is set, otherwise report will return month to date (iso-8601, UTC)."),
        granularity: GranularityEnum = Query(default="None", description="The granularity of rows in the query.")
    ):
        self.from_date = from_date
        self.to_date = to_date
        self.granularity = granularity


@costs_core_router.get("/costs", response_model=CostReport, name=strings.API_GET_COSTS,
                       responses=get_cost_report_responses())
async def costs(
        params: CostsQueryParams = Depends(),
        cost_service: CostService = Depends(cost_service_factory),
        workspace_repo=Depends(get_repository(WorkspaceRepository)),
        shared_services_repo=Depends(get_repository(SharedServiceRepository)),
        costs_repo=Depends(get_repository(CostsRepository))) -> CostReport:

    validate_report_period(params.from_date, params.to_date)
    try:
        async with cost_query_errors("Failed to query Azure TRE costs"):
            return await cost_service.query_tre_costs(
                config.TRE_ID, params.granularity, params.from_date, params.to_date,
                workspace_repo, shared_services_repo, costs_repo)
    except RetryableCostError as e:
        return e.as_response()


@costs_workspace_router.get("/workspaces/{workspace_id}/costs", response_model=WorkspaceCostReport,
                            name=strings.API_GET_WORKSPACE_COSTS,
                            dependencies=[Depends(get_current_workspace_owner_or_tre_admin)],
                            responses=get_workspace_cost_report_responses())
async def workspace_costs(workspace_id: UUID4, params: CostsQueryParams = Depends(),
                          cost_service: CostService = Depends(cost_service_factory),
                          workspace_repo=Depends(get_repository(WorkspaceRepository)),
                          workspace_services_repo=Depends(get_repository(WorkspaceServiceRepository)),
                          user_resource_repo=Depends(get_repository(UserResourceRepository)),
                          costs_repo=Depends(get_repository(CostsRepository))) -> WorkspaceCostReport:

    validate_report_period(params.from_date, params.to_date)
    try:
        async with cost_query_errors("Failed to query Azure TRE costs"):
            return await cost_service.query_tre_workspace_costs(
                str(workspace_id), params.granularity, params.from_date, params.to_date,
                workspace_repo, workspace_services_repo, user_resource_repo, costs_repo)
    except RetryableCostError as e:
        return e.as_response()


@costs_internal_router.get("/internal/costs/subscriptions", name=strings.API_GET_COST_SUBSCRIPTIONS)
async def cost_subscriptions(
        cost_service: CostService = Depends(cost_service_factory),
        workspace_repo=Depends(get_repository(WorkspaceRepository))) -> JSONResponse:
    """List the subscriptions TRE costs are incurred in (core plus any workspace subscriptions).

    The Cost Processor runs one Cost Management export per subscription and needs to know which
    ones to cover. Authenticated via the Cost Processor managed identity.
    """
    async with cost_query_errors("Failed to list Azure TRE cost subscriptions",
                                 strings.API_GET_COST_SUBSCRIPTIONS_INTERNAL_SERVER_ERROR):
        subscription_ids = await cost_service.get_subscription_ids(workspace_repo)
        return JSONResponse(content={"subscription_ids": subscription_ids})


@costs_internal_router.post("/internal/costs/ingest", name=strings.API_INGEST_COSTS,
                            status_code=status.HTTP_202_ACCEPTED)
async def ingest_costs(
        payload: CostIngestRequest,
        cost_service: CostService = Depends(cost_service_factory),
        workspace_repo=Depends(get_repository(WorkspaceRepository)),
        costs_repo=Depends(get_repository(CostsRepository))) -> JSONResponse:
    """Persist cost rows produced by a Cost Management export for a closed month.

    Used by the Cost Processor for history backfill and month finalisation, which run one-time
    Cost Management exports rather than Query API requests. Authenticated via the Cost Processor
    managed identity.
    """
    # the period is an inclusive range of days, so a single-day ingest has from_date == to_date
    if payload.from_date > payload.to_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=strings.API_INGEST_COSTS_TO_DATE_BEFORE_FROM_DATE)
    async with cost_query_errors("Failed to ingest exported Azure TRE costs",
                                 strings.API_INGEST_COSTS_INTERNAL_SERVER_ERROR):
        collected = await cost_service.ingest_export_costs(
            config.TRE_ID, payload.granularity,
            # the payload carries dates; the service works in datetimes, anchored at midnight UTC
            datetime.combine(payload.from_date, time.min),
            datetime.combine(payload.to_date, time.min),
            payload.rows, workspace_repo, costs_repo, payload.subscription_id)
        return JSONResponse(content=collected, status_code=status.HTTP_202_ACCEPTED)


@costs_internal_router.post("/internal/costs/refresh", name=strings.API_REFRESH_COSTS,
                            status_code=status.HTTP_202_ACCEPTED)
async def refresh_costs(
        params: CostsQueryParams = Depends(),
        cost_service: CostService = Depends(cost_service_factory),
        workspace_repo=Depends(get_repository(WorkspaceRepository)),
        costs_repo=Depends(get_repository(CostsRepository))) -> JSONResponse:
    """Query Cost Management for the period and persist it into the cost collection.
    Authenticated via the Cost Processor managed identity.
    """
    validate_report_period(params.from_date, params.to_date)
    try:
        async with cost_query_errors("Failed to refresh Azure TRE costs"):
            collected = await cost_service.refresh_costs(
                config.TRE_ID, params.granularity, params.from_date, params.to_date, workspace_repo, costs_repo)
            return JSONResponse(content=collected, status_code=status.HTTP_202_ACCEPTED)
    except RetryableCostError as e:
        return e.as_response()
