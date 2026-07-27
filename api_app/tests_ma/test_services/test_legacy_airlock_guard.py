from mock import AsyncMock, patch
import pytest

from services.legacy_airlock_guard import run_legacy_airlock_migration_guard, \
    ensure_workspace_airlock_version_supported, ensure_airlock_version_change_allowed
from models.schemas.resource import ResourcePatch


def _workspace(airlock_version=None):
    ws = AsyncMock()
    ws.id = "0b9c8928-9f25-4522-8f48-595105516531"
    ws.properties = {} if airlock_version is None else {"airlock_version": airlock_version}
    return ws


def test_ensure_workspace_airlock_version_supported_allows_when_legacy_enabled():
    with patch("services.legacy_airlock_guard.config.ENABLE_LEGACY_AIRLOCK", new=True):
        # No exception even for a v1 workspace when legacy is enabled
        ensure_workspace_airlock_version_supported({"enable_airlock": True, "airlock_version": 1})


def test_ensure_workspace_airlock_version_supported_allows_v2_when_legacy_disabled():
    with patch("services.legacy_airlock_guard.config.ENABLE_LEGACY_AIRLOCK", new=False):
        ensure_workspace_airlock_version_supported({"enable_airlock": True, "airlock_version": 2})


def test_ensure_workspace_airlock_version_supported_blocks_v1_when_legacy_disabled():
    with patch("services.legacy_airlock_guard.config.ENABLE_LEGACY_AIRLOCK", new=False):
        with pytest.raises(ValueError):
            ensure_workspace_airlock_version_supported({"enable_airlock": True, "airlock_version": 1})


@pytest.mark.asyncio
async def test_ensure_airlock_version_change_allowed_noop_when_version_unchanged():
    request_repo = AsyncMock()
    await ensure_airlock_version_change_allowed(_workspace(1), ResourcePatch(properties={"airlock_version": 1}), request_repo)
    request_repo.get_in_flight_airlock_request_ids_for_workspace.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_airlock_version_change_allowed_noop_when_no_version_in_patch():
    request_repo = AsyncMock()
    await ensure_airlock_version_change_allowed(_workspace(1), ResourcePatch(properties={"display_name": "x"}), request_repo)
    request_repo.get_in_flight_airlock_request_ids_for_workspace.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_airlock_version_change_allowed_permits_change_when_no_in_flight():
    request_repo = AsyncMock()
    request_repo.get_in_flight_airlock_request_ids_for_workspace.return_value = []
    await ensure_airlock_version_change_allowed(_workspace(1), ResourcePatch(properties={"airlock_version": 2}), request_repo)


@pytest.mark.asyncio
async def test_ensure_airlock_version_change_allowed_blocks_upgrade_with_in_flight_requests():
    request_repo = AsyncMock()
    request_repo.get_in_flight_airlock_request_ids_for_workspace.return_value = ["req-1"]
    with pytest.raises(ValueError):
        await ensure_airlock_version_change_allowed(_workspace(1), ResourcePatch(properties={"airlock_version": 2}), request_repo)


@pytest.mark.asyncio
@patch("services.legacy_airlock_guard.WorkspaceRepository.create")
@patch("services.legacy_airlock_guard.AirlockRequestRepository.create")
async def test_guard_returns_when_legacy_airlock_enabled(request_repo_create_mock, workspace_repo_create_mock):
    with patch("services.legacy_airlock_guard.config.ENABLE_LEGACY_AIRLOCK", new=True):
        await run_legacy_airlock_migration_guard()

    workspace_repo_create_mock.assert_not_called()
    request_repo_create_mock.assert_not_called()


@pytest.mark.asyncio
@patch("services.legacy_airlock_guard.logger")
@patch("services.legacy_airlock_guard.WorkspaceRepository.create")
@patch("services.legacy_airlock_guard.AirlockRequestRepository.create")
async def test_guard_logs_info_when_no_v1_dependencies(request_repo_create_mock, workspace_repo_create_mock, logger_mock):
    workspace_repo = AsyncMock()
    workspace_repo.get_active_v1_workspace_ids.return_value = []
    workspace_repo_create_mock.return_value = workspace_repo

    request_repo = AsyncMock()
    request_repo.get_in_flight_v1_airlock_request_ids.return_value = []
    request_repo_create_mock.return_value = request_repo

    with patch("services.legacy_airlock_guard.config.ENABLE_LEGACY_AIRLOCK", new=False), \
            patch("services.legacy_airlock_guard.config.BLOCK_DISABLE_LEGACY_AIRLOCK_IF_V1_EXISTS", new=False):
        await run_legacy_airlock_migration_guard()

    logger_mock.info.assert_called_once()
    logger_mock.warning.assert_not_called()


@pytest.mark.asyncio
@patch("services.legacy_airlock_guard.logger")
@patch("services.legacy_airlock_guard.WorkspaceRepository.create")
@patch("services.legacy_airlock_guard.AirlockRequestRepository.create")
async def test_guard_logs_warning_when_v1_dependencies_exist_and_blocking_disabled(request_repo_create_mock, workspace_repo_create_mock, logger_mock):
    workspace_repo = AsyncMock()
    workspace_repo.get_active_v1_workspace_ids.return_value = ["workspace-1"]
    workspace_repo_create_mock.return_value = workspace_repo

    request_repo = AsyncMock()
    request_repo.get_in_flight_v1_airlock_request_ids.return_value = ["request-1"]
    request_repo_create_mock.return_value = request_repo

    with patch("services.legacy_airlock_guard.config.ENABLE_LEGACY_AIRLOCK", new=False), \
            patch("services.legacy_airlock_guard.config.BLOCK_DISABLE_LEGACY_AIRLOCK_IF_V1_EXISTS", new=False):
        await run_legacy_airlock_migration_guard()

    logger_mock.warning.assert_called_once()


@pytest.mark.asyncio
@patch("services.legacy_airlock_guard.WorkspaceRepository.create")
@patch("services.legacy_airlock_guard.AirlockRequestRepository.create")
async def test_guard_blocks_when_v1_dependencies_exist_and_blocking_enabled(request_repo_create_mock, workspace_repo_create_mock):
    workspace_repo = AsyncMock()
    workspace_repo.get_active_v1_workspace_ids.return_value = ["workspace-1"]
    workspace_repo_create_mock.return_value = workspace_repo

    request_repo = AsyncMock()
    request_repo.get_in_flight_v1_airlock_request_ids.return_value = []
    request_repo_create_mock.return_value = request_repo

    with patch("services.legacy_airlock_guard.config.ENABLE_LEGACY_AIRLOCK", new=False), \
            patch("services.legacy_airlock_guard.config.BLOCK_DISABLE_LEGACY_AIRLOCK_IF_V1_EXISTS", new=True):
        with pytest.raises(RuntimeError):
            await run_legacy_airlock_migration_guard()
