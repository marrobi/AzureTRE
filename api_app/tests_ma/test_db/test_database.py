import pytest
from unittest.mock import AsyncMock, patch
from db.database import Database


@pytest.mark.asyncio
@patch('db.database.Database._create_container_if_not_exists', new_callable=AsyncMock)
@patch('db.database.Database.get_database_proxy', new_callable=AsyncMock)
async def test_bootstrap_database_success(mock_get_database_proxy, mock_create_container_if_not_exists):

    mock_get_database_proxy.return_value = AsyncMock()
    mock_create_container_if_not_exists.return_value = None

    result = await Database.bootstrap_database()

    assert result is True
    mock_get_database_proxy.assert_called_once()
    assert mock_create_container_if_not_exists.call_count == 5


@pytest.mark.asyncio
@patch('db.database.logger')
@patch('db.database.Database._create_container_if_not_exists', new_callable=AsyncMock)
@patch('db.database.Database.get_database_proxy', new_callable=AsyncMock)
async def test_bootstrap_database_failure(mock_get_database_proxy, mock_create_container_if_not_exists, mock_logger):

    mock_get_database_proxy.side_effect = Exception("Test exception")

    result = await Database.bootstrap_database()

    assert result is False
    mock_get_database_proxy.assert_called_once()
    mock_logger.exception.assert_called_once_with("Could not bootstrap database")


@pytest.mark.asyncio
async def test_create_container_if_not_exists():
    mock_database_proxy = AsyncMock()
    container_name = "test_container"
    partition_key_path = "/test"

    await Database._create_container_if_not_exists(mock_database_proxy, container_name, partition_key_path)

    mock_database_proxy.create_container_if_not_exists.assert_called_once_with(
        id=container_name,
        partition_key={
            'paths': [partition_key_path],
            'kind': 'Hash'
        }
    )
