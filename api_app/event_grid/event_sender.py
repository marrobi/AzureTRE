import re
import json

from typing import Dict, Optional
from azure.eventgrid import EventGridEvent
from models.domain.events import AirlockNotificationRequestData, AirlockNotificationWorkspaceData, StatusChangedData, AirlockNotificationData
from event_grid.helpers import publish_event
from core import config
from models.domain.airlock_request import AirlockRequest, AirlockRequestStatus
from models.domain.workspace import Workspace
from resources import constants
from services.logging import logger


def _resolve_workspace_storage_account_names(workspace: Workspace, unique_identifier_suffix: str) -> Dict[str, str]:
    # Resolve the workspace-scoped airlock storage account names, preferring the actual names
    # exposed by the workspace bundle (single source of truth). Fall back to building them from the
    # unique_identifier_suffix for workspaces created before the properties existed (#2893, #3666).
    def resolve(property_name: str, name_constant: str) -> str:
        return workspace.properties.get(property_name) or name_constant.format(unique_identifier_suffix)

    return {
        "import_approved_storage_name": resolve("import_approved_storage_name", constants.STORAGE_ACCOUNT_NAME_IMPORT_APPROVED),
        "export_internal_storage_name": resolve("export_internal_storage_name", constants.STORAGE_ACCOUNT_NAME_EXPORT_INTERNAL),
        "export_inprogress_storage_name": resolve("export_inprogress_storage_name", constants.STORAGE_ACCOUNT_NAME_EXPORT_INPROGRESS),
        "export_rejected_storage_name": resolve("export_rejected_storage_name", constants.STORAGE_ACCOUNT_NAME_EXPORT_REJECTED),
        "export_blocked_storage_name": resolve("export_blocked_storage_name", constants.STORAGE_ACCOUNT_NAME_EXPORT_BLOCKED),
    }


async def send_status_changed_event(airlock_request: AirlockRequest, previous_status: Optional[AirlockRequestStatus], workspace: Workspace):
    request_id = airlock_request.id
    new_status = airlock_request.status.value
    previous_status = previous_status.value if previous_status else None
    request_type = airlock_request.type.value
    short_workspace_id = airlock_request.workspaceId[-4:]
    # The suffix used to build the workspace-scoped airlock storage account names. Fall back to the
    # last 4 characters of the workspace id for workspaces created before the property existed.
    unique_identifier_suffix = workspace.properties.get("unique_identifier_suffix") or short_workspace_id
    # The resolved workspace-scoped storage account names, passed on the event so the airlock
    # processor uses them directly instead of re-deriving them from the suffix.
    workspace_storage_account_names = _resolve_workspace_storage_account_names(workspace, unique_identifier_suffix)

    status_changed_event = EventGridEvent(
        event_type="statusChanged",
        data=StatusChangedData(request_id=request_id, new_status=new_status, previous_status=previous_status, type=request_type, workspace_id=short_workspace_id, unique_identifier_suffix=unique_identifier_suffix, **workspace_storage_account_names).__dict__,
        subject=f"{request_id}/statusChanged",
        data_version="2.0"
    )
    logger.info(f"Sending status changed event with request ID {request_id}, new status: {new_status}, previous status: {previous_status}")
    await publish_event(status_changed_event, config.EVENT_GRID_STATUS_CHANGED_TOPIC_ENDPOINT)


async def send_airlock_notification_event(airlock_request: AirlockRequest, workspace: Workspace, role_assignment_details: Dict[str, str]):
    def to_snake_case(string: str):
        return re.sub(r'(?<!^)(?=[A-Z])', '_', string).lower()

    request_id = airlock_request.id
    status = airlock_request.status.value
    recipient_emails_by_role = {to_snake_case(role_name): role_id for role_name, role_id in role_assignment_details.items()}

    data = AirlockNotificationData(
        event_type="status_changed",
        recipient_emails_by_role=recipient_emails_by_role,
        request=AirlockNotificationRequestData(
            id=request_id,
            created_when=airlock_request.createdWhen,
            created_by=airlock_request.createdBy,
            updated_when=airlock_request.updatedWhen,
            updated_by=airlock_request.updatedBy,
            request_type=airlock_request.type,
            files=airlock_request.files,
            status=airlock_request.status.value,
            business_justification=airlock_request.businessJustification),
        workspace=AirlockNotificationWorkspaceData(
            id=workspace.id,
            display_name=workspace.properties["display_name"],
            description=workspace.properties["description"]),
    )

    # For EventGridEvent, data should be a Dict[str, object]
    # Becuase data has nested objects, they all need to be recursively converted to dict
    # To do that, we use a json() method implemented for all objects in AzureTREModel, and convert it back from json
    data_dict = json.loads(data.json())

    airlock_notification = EventGridEvent(
        event_type="airlockNotification",
        data=data_dict,
        subject=f"{request_id}/airlockNotification",
        data_version="4.0"
    )

    logger.info(f"Sending airlock notification event with request ID {request_id}, status: {status}")
    await publish_event(airlock_notification, config.EVENT_GRID_AIRLOCK_NOTIFICATION_TOPIC_ENDPOINT)
