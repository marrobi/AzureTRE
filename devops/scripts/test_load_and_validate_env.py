import json
import pytest
from unittest.mock import patch, mock_open

from devops.scripts.load_and_validate_env import (
    load_yaml,
    check_duplicate_keys,
    validate_schema,
    format_for_env_export,
    convert_azure_env_to_arm_env,
    construct_tre_url,
)


@pytest.mark.asyncio
def test_load_yaml():
    mock_file_content = "key: value"
    with patch("builtins.open", mock_open(read_data=mock_file_content)):
        result = load_yaml("dummy_path")
        assert result == {"key": "value"}


@pytest.mark.asyncio
def test_check_duplicate_keys():
    yaml_content = {
        "key1": "value1",
        "key2": {
            "key3": "value3",
            "key1": "value4"
        }
    }
    result = check_duplicate_keys(yaml_content)
    assert result == "key1"


@pytest.mark.asyncio
def test_validate_schema():
    yaml_content = {"key": "value"}
    schema_content = {
        "type": "object",
        "properties": {
            "key": {"type": "string"}
        }
    }
    with patch("builtins.open", mock_open(read_data=json.dumps(schema_content))):
        result = validate_schema(yaml_content, "dummy_schema_path")
        assert result is None

    invalid_yaml_content = {"key": 123}
    with patch("builtins.open", mock_open(read_data=json.dumps(schema_content))):
        result = validate_schema(invalid_yaml_content, "dummy_schema_path")
        assert "123 is not of type 'string'" in result


@pytest.mark.asyncio
def test_format_for_env_export():
    content = {
        "key1": "value1",
        "key2": True,
        "key3": [1, 2, 3]
    }
    result = format_for_env_export(content)
    assert result == {
        "key1": "value1",
        "key2": "true",
        "key3": "'[\"1\",\"2\",\"3\"]'"
    }


@pytest.mark.asyncio
def test_convert_azure_env_to_arm_env():
    assert convert_azure_env_to_arm_env("AzureCloud") == "public"
    assert convert_azure_env_to_arm_env("AzureUSGovernment") == "usgovernment"
    assert convert_azure_env_to_arm_env("UnknownEnv") is None


@pytest.mark.asyncio
def test_construct_tre_url():
    result = construct_tre_url("tre-id", "location", "AzureCloud")
    assert result == "https://tre-id.location.cloudapp.azure.com"

    result = construct_tre_url("tre-id", "location", "AzureUSGovernment")
    assert result == "https://tre-id.location.cloudapp.usgovcloudapi.net"
