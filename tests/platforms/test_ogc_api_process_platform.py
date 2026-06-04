import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _install_ogc_api_processes_client_stub():
    root_module = types.ModuleType("ogc_api_processes_client")
    api_client_wrapper_module = types.ModuleType(
        "ogc_api_processes_client.api_client_wrapper"
    )
    configuration_module = types.ModuleType(
        "ogc_api_processes_client.configuration"
    )
    models_module = types.ModuleType("ogc_api_processes_client.models")
    inline_or_ref_data_module = types.ModuleType(
        "ogc_api_processes_client.models.inline_or_ref_data"
    )
    input_value_no_object_module = types.ModuleType(
        "ogc_api_processes_client.models.input_value_no_object"
    )
    link_module = types.ModuleType("ogc_api_processes_client.models.link")
    qualified_input_value_module = types.ModuleType(
        "ogc_api_processes_client.models.qualified_input_value"
    )
    status_code_module = types.ModuleType("ogc_api_processes_client.models.status_code")
    status_info_module = types.ModuleType("ogc_api_processes_client.models.status_info")

    class ApiClientWrapper:
        pass

    class Configuration:
        def __init__(self, host):
            self.host = host

    class InlineOrRefData:
        pass

    class InputValueNoObject:
        pass

    class Link:
        pass

    class QualifiedInputValue:
        pass

    class StatusCode:
        ACCEPTED = "accepted"
        RUNNING = "running"
        DISMISSED = "dismissed"
        SUCCESSFUL = "successful"
        FAILED = "failed"

    class StatusInfo:
        pass

    api_client_wrapper_module.ApiClientWrapper = ApiClientWrapper
    configuration_module.Configuration = Configuration
    inline_or_ref_data_module.InlineOrRefData = InlineOrRefData
    input_value_no_object_module.InputValueNoObject = InputValueNoObject
    link_module.Link = Link
    qualified_input_value_module.QualifiedInputValue = QualifiedInputValue
    status_code_module.StatusCode = StatusCode
    status_info_module.StatusInfo = StatusInfo

    sys.modules["ogc_api_processes_client"] = root_module
    sys.modules["ogc_api_processes_client.api_client_wrapper"] = (
        api_client_wrapper_module
    )
    sys.modules["ogc_api_processes_client.configuration"] = configuration_module
    sys.modules["ogc_api_processes_client.models"] = models_module
    sys.modules["ogc_api_processes_client.models.inline_or_ref_data"] = (
        inline_or_ref_data_module
    )
    sys.modules["ogc_api_processes_client.models.input_value_no_object"] = (
        input_value_no_object_module
    )
    sys.modules["ogc_api_processes_client.models.link"] = link_module
    sys.modules["ogc_api_processes_client.models.qualified_input_value"] = (
        qualified_input_value_module
    )
    sys.modules["ogc_api_processes_client.models.status_code"] = status_code_module
    sys.modules["ogc_api_processes_client.models.status_info"] = status_info_module


try:
    import ogc_api_processes_client  # noqa: F401
except ModuleNotFoundError:
    _install_ogc_api_processes_client_stub()

from app.platforms.implementations.ogc_api_process import (  # noqa: E402
    GEOJSON_FEATURECOLLECTION_SCHEMA,
    OGCAPIProcessPlatform,
    STAC_COLLECTION_SCHEMA,
)
from app.schemas.enum import (  # noqa: E402
    OutputFormatEnum,
    ProcessingStatusEnum,
)
from app.schemas.parameters import ParamTypeEnum, Parameter  # noqa: E402
from app.schemas.unit_job import ServiceDetails  # noqa: E402


@pytest.fixture
def platform():
    return OGCAPIProcessPlatform()


def build_input(description, min_occurs, schema):
    return SimpleNamespace(
        description=description,
        min_occurs=min_occurs,
        model_dump=lambda: {
            "var_schema": {
                "actual_instance": schema,
            }
        },
    )


def build_collection_payload(collection_id="collection-1", title="Test Collection"):
    return {
        "id": collection_id,
        "stac_version": "1.0.0",
        "title": title,
        "description": "Test STAC collection",
        "type": "Collection",
        "license": "proprietary",
        "links": [],
        "extent": {
            "spatial": {"bbox": [[-180.0, -90.0, 180.0, 90.0]]},
            "temporal": {"interval": [[None, None]]},
        },
    }


@pytest.mark.parametrize(
    ("schema", "input_id", "expected_type"),
    [
        ({"format": "date-time"}, "datetime", ParamTypeEnum.DATETIME),
        (
            {"type": "array", "subtype": "date-interval"},
            "temporal_extent",
            ParamTypeEnum.DATE_INTERVAL,
        ),
        (
            {"type": "object", "subtype": "bounding-box"},
            "spatial_extent",
            ParamTypeEnum.BOUNDING_BOX,
        ),
        (GEOJSON_FEATURECOLLECTION_SCHEMA, "area", ParamTypeEnum.POLYGON),
        ({"format": "geojson"}, "area", ParamTypeEnum.POLYGON),
        ({"type": "object", "subtype": "geojson"}, "area", ParamTypeEnum.POLYGON),
        (
            {"type": "object", "properties": {"features": {"type": "array"}}},
            "area",
            ParamTypeEnum.POLYGON,
        ),
        ({"type": "boolean"}, "enabled", ParamTypeEnum.BOOLEAN),
        ({"type": "integer"}, "limit", ParamTypeEnum.INTEGER),
        ({"type": "double"}, "scale", ParamTypeEnum.DOUBLE),
        (
            {"type": "object", "required": ["coordinates", "type", "bbox"],
             "properties": {
                 "type": {
                     "actual_instance": {
                        "actual_instance": {
                            "enum": ["Polygon"]
                        }
                     }
                 }
             }
             },
            "bbox",
            ParamTypeEnum.POLYGON,
        ),
        (
            {"type": "array", "items": {"type": "string"}},
            "bands",
            ParamTypeEnum.ARRAY_STRING,
        ),
        ({"type": "number"}, "threshold", ParamTypeEnum.DOUBLE),
        ({"type": "string"}, "mode", ParamTypeEnum.STRING),
        (
            {"oneOf": [{"type": "string"}, {"format": "geojson"}]},
            "geometry",
            ParamTypeEnum.POLYGON,
        ),
    ],
)
def test_get_type_from_schema(platform, schema, input_id, expected_type):
    assert platform._get_type_from_schema(schema, input_id) == expected_type


@pytest.mark.parametrize(
    ("job_id", "expected"),
    [
        ("namespace:job-123", ("namespace", "job-123")),
        ("job-123", ("", "job-123")),
    ],
)
def test_split_job_id(platform, job_id, expected):
    assert platform._split_job_id(job_id) == expected


@pytest.mark.parametrize(
    ("ogc_status, expected_status"),
    [
        ("accepted", ProcessingStatusEnum.CREATED),
        ("running", ProcessingStatusEnum.RUNNING),
        ("dismissed", ProcessingStatusEnum.CANCELED),
        ("successful", ProcessingStatusEnum.FINISHED),
        ("failed", ProcessingStatusEnum.FAILED),
        ("unknown", ProcessingStatusEnum.UNKNOWN),
        (None, ProcessingStatusEnum.UNKNOWN),
    ],
)
def test_map_ogcapi_status(platform, ogc_status, expected_status):
    assert platform._map_ogcapi_status(ogc_status) == expected_status


@pytest.mark.asyncio
@patch("app.platforms.implementations.ogc_api_process.ApiClientWrapper")
async def test_create_api_client_instance_without_namespace(mock_api_client, platform):
    await platform._create_api_client_instance("https://example.com", "", None)

    configuration = mock_api_client.call_args.args[0]
    assert configuration.host == "https://example.com"
    assert mock_api_client.call_args.kwargs == {}


@pytest.mark.asyncio
@patch("app.platforms.implementations.ogc_api_process.ApiClientWrapper")
async def test_create_api_client_instance_with_token_and_namespace(
    mock_api_client, platform
):
    await platform._create_api_client_instance(
        "https://example.com", "ns", "exchanged-token"
    )

    configuration = mock_api_client.call_args.args[0]
    assert configuration.host == "https://example.com/ns"
    assert mock_api_client.call_args.kwargs == {
        "header_name": "Authorization",
        "header_value": "Bearer exchanged-token",
    }


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.ogc_api_process.exchange_token",
    new_callable=AsyncMock,
)
@patch("app.platforms.implementations.ogc_api_process.get_current_user_claims")
@patch.object(OGCAPIProcessPlatform, "_create_api_client_instance", new_callable=AsyncMock)
async def test_execute_job_returns_namespaced_job_id(
    mock_create_api_client, mock_get_current_user_claims, mock_exchange_token, platform
):
    mock_exchange_token.return_value = "exchanged-token"
    mock_get_current_user_claims.return_value = {
        "sub": "user-123",
        "preferred_username": "alice",
        "email": "alice@example.com",
    }
    api_client = MagicMock()
    api_client.execute_simple.return_value = SimpleNamespace(job_id="job-123")
    mock_create_api_client.return_value = api_client

    result = await platform.execute_job(
        user_token="token",
        title="My job",
        details=ServiceDetails(
            endpoint="https://example.com",
            namespace="ns",
            application="buffer",
        ),
        parameters={"geometry": {"type": "Polygon"}},
        format=OutputFormatEnum.GEOTIFF,
    )

    assert result == "ns:job-123"
    api_client.execute_simple.assert_called_once_with(
        process_id="buffer",
        execute={
            "inputs": {"geometry": {"type": "Polygon"}},
            "properties": {
                "title": "My job",
                "application": "buffer",
                "user_id": "user-123",
                "username": "alice",
                "email": "alice@example.com",
            },
        },
        _headers={
            "accept": "*/*",
            "Content-Type": "application/json",
            "Authorization": "Bearer exchanged-token",
        },
    )


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.ogc_api_process.exchange_token",
    new_callable=AsyncMock,
)
@patch("app.platforms.implementations.ogc_api_process.get_current_user_claims")
@patch.object(OGCAPIProcessPlatform, "_create_api_client_instance", new_callable=AsyncMock)
async def test_execute_job_returns_plain_job_id_without_namespace(
    mock_create_api_client, mock_get_current_user_claims, mock_exchange_token, platform
):
    mock_exchange_token.return_value = None
    mock_get_current_user_claims.return_value = {"sub": "user-123"}
    api_client = MagicMock()
    api_client.execute_simple.return_value = SimpleNamespace(job_id="job-123")
    mock_create_api_client.return_value = api_client

    result = await platform.execute_job(
        user_token="token",
        title="My job",
        details=ServiceDetails(
            endpoint="https://example.com",
            application="buffer",
        ),
        parameters={"limit": 10},
        format=OutputFormatEnum.GEOTIFF,
    )

    assert result == "job-123"
    api_client.execute_simple.assert_called_once_with(
        process_id="buffer",
        execute={
            "inputs": {"limit": 10},
            "properties": {
                "title": "My job",
                "application": "buffer",
                "user_id": "user-123",
            },
        },
        _headers={
            "accept": "*/*",
            "Content-Type": "application/json",
        },
    )


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.ogc_api_process.exchange_token",
    new_callable=AsyncMock,
)
@patch("app.platforms.implementations.ogc_api_process.get_current_user_claims")
@patch.object(OGCAPIProcessPlatform, "_create_api_client_instance", new_callable=AsyncMock)
async def test_execute_job_omits_missing_optional_user_fields(
    mock_create_api_client, mock_get_current_user_claims, mock_exchange_token, platform
):
    mock_exchange_token.return_value = "exchanged-token"
    mock_get_current_user_claims.return_value = {}
    api_client = MagicMock()
    api_client.execute_simple.return_value = SimpleNamespace(job_id="job-123")
    mock_create_api_client.return_value = api_client

    await platform.execute_job(
        user_token="token",
        title="My job",
        details=ServiceDetails(
            endpoint="https://example.com",
            application="buffer",
        ),
        parameters={"limit": 10},
        format=OutputFormatEnum.GEOTIFF,
    )

    api_client.execute_simple.assert_called_once_with(
        process_id="buffer",
        execute={
            "inputs": {"limit": 10},
            "properties": {"title": "My job", "application": "buffer"},
        },
        _headers={
            "accept": "*/*",
            "Content-Type": "application/json",
            "Authorization": "Bearer exchanged-token",
        },
    )


@pytest.mark.asyncio
async def test_execute_synchronous_job_not_implemented(platform):
    with pytest.raises(NotImplementedError, match="not implemented yet"):
        await platform.execute_synchronous_job(
            user_token="token",
            title="My job",
            details=ServiceDetails(
                endpoint="https://example.com",
                application="buffer",
            ),
            parameters={},
            format=OutputFormatEnum.GEOTIFF,
        )


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.ogc_api_process.exchange_token",
    new_callable=AsyncMock,
)
@patch.object(OGCAPIProcessPlatform, "_create_api_client_instance", new_callable=AsyncMock)
async def test_get_job_status_maps_client_status(
    mock_create_api_client, mock_exchange_token, platform
):
    mock_exchange_token.return_value = "exchanged-token"
    api_client = MagicMock()
    api_client.get_status.return_value = SimpleNamespace(status="running")
    mock_create_api_client.return_value = api_client

    result = await platform.get_job_status(
        user_token="token",
        job_id="ns:job-123",
        details=ServiceDetails(
            endpoint="https://example.com",
            namespace="ignored-by-job-id",
            application="buffer",
        ),
    )

    assert result == ProcessingStatusEnum.RUNNING
    mock_create_api_client.assert_awaited_once_with(
        "https://example.com", "ns", "exchanged-token"
    )
    api_client.get_status.assert_called_once_with(job_id="job-123")


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.ogc_api_process.exchange_token",
    new_callable=AsyncMock,
)
@patch.object(OGCAPIProcessPlatform, "_create_api_client_instance", new_callable=AsyncMock)
async def test_get_job_results_returns_stac_collection(
    mock_create_api_client, mock_exchange_token, platform
):
    mock_exchange_token.return_value = "exchanged-token"
    api_client = MagicMock()
    api_client.get_result.return_value = {
        "result": SimpleNamespace(
            actual_instance=SimpleNamespace(
                var_schema=SimpleNamespace(actual_instance=STAC_COLLECTION_SCHEMA),
                value=SimpleNamespace(
                    actual_instance=build_collection_payload("collection-from-stac")
                ),
            )
        )
    }
    mock_create_api_client.return_value = api_client

    result = await platform.get_job_results(
        user_token="token",
        job_id="ns:job-123",
        details=ServiceDetails(
            endpoint="https://example.com",
            namespace="ns",
            application="buffer",
        ),
    )

    assert result.id == "collection-from-stac"
    assert result.title == "Test Collection"


@pytest.mark.asyncio
@patch("app.platforms.implementations.ogc_api_process.http_get")
@patch(
    "app.platforms.implementations.ogc_api_process.exchange_token",
    new_callable=AsyncMock,
)
@patch.object(OGCAPIProcessPlatform, "_create_api_client_instance", new_callable=AsyncMock)
async def test_get_job_results_follows_geojson_collection_link(
    mock_create_api_client, mock_exchange_token, mock_http_get, platform
):
    mock_exchange_token.return_value = "exchanged-token"
    api_client = MagicMock()
    api_client.get_result.return_value = {
        "result": SimpleNamespace(
            actual_instance=SimpleNamespace(
                var_schema=SimpleNamespace(
                    actual_instance=GEOJSON_FEATURECOLLECTION_SCHEMA
                ),
                value=SimpleNamespace(
                    oneof_schema_2_validator={
                        "features": [
                            {
                                "links": [
                                    {
                                        "rel": "collection",
                                        "href": "https://example.com/collections/1",
                                    }
                                ]
                            }
                        ]
                    }
                ),
            )
        )
    }
    mock_create_api_client.return_value = api_client
    mock_http_get.return_value = MagicMock()
    mock_http_get.return_value.json.return_value = build_collection_payload(
        "collection-from-geojson"
    )

    result = await platform.get_job_results(
        user_token="token",
        job_id="ns:job-123",
        details=ServiceDetails(
            endpoint="https://example.com",
            namespace="ns",
            application="buffer",
        ),
    )

    assert result.id == "collection-from-geojson"
    mock_http_get.assert_called_once_with(
        "https://example.com/collections/1",
        follow_redirects=True,
        headers={"Authorization": "Bearer exchanged-token"},
    )
    mock_http_get.return_value.raise_for_status.assert_called_once_with()


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.ogc_api_process.exchange_token",
    new_callable=AsyncMock,
)
@patch.object(OGCAPIProcessPlatform, "_create_api_client_instance", new_callable=AsyncMock)
async def test_get_job_results_returns_empty_collection_when_no_supported_result(
    mock_create_api_client, mock_exchange_token, platform
):
    mock_exchange_token.return_value = "exchanged-token"
    api_client = MagicMock()
    api_client.get_result.return_value = {
        "result": SimpleNamespace(actual_instance=None)
    }
    mock_create_api_client.return_value = api_client

    result = await platform.get_job_results(
        user_token="token",
        job_id="ns:job-123",
        details=ServiceDetails(
            endpoint="https://example.com",
            namespace="ns",
            application="buffer",
        ),
    )

    assert result.id == "ns-job-123"
    assert result.title == "Results for buffer"
    assert result.license == "proprietary"


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.ogc_api_process.exchange_token",
    new_callable=AsyncMock,
)
@patch.object(OGCAPIProcessPlatform, "_create_api_client_instance", new_callable=AsyncMock)
async def test_get_service_parameters_maps_geojson_and_options(
    mock_create_api_client, mock_exchange_token, platform
):
    mock_exchange_token.return_value = "exchanged-token"

    geojson_input = build_input(
        "Area of interest",
        1,
        {
            "oneOf": [
                {"type": "string"},
                {"format": "geojson"},
            ]
        },
    )
    enum_input = build_input(
        "Output mode",
        0,
        {
            "type": "string",
            "enum": ["fast", "accurate"],
        },
    )

    api_client = MagicMock()
    api_client.get_process_description.return_value = SimpleNamespace(
        inputs={
            "geometry": geojson_input,
            "mode": enum_input,
        }
    )
    mock_create_api_client.return_value = api_client

    result = await platform.get_service_parameters(
        user_token="token",
        details=ServiceDetails(
            endpoint="https://example.com",
            namespace="ns",
            application="my-process",
        ),
    )

    assert result == [
        Parameter(
            name="geometry",
            description="Area of interest",
            default=None,
            optional=False,
            type=ParamTypeEnum.POLYGON,
            options=[],
        ),
        Parameter(
            name="mode",
            description="Output mode",
            default=None,
            optional=True,
            type=ParamTypeEnum.STRING,
            options=["fast", "accurate"],
        ),
    ]


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.ogc_api_process.exchange_token",
    new_callable=AsyncMock,
)
@patch.object(OGCAPIProcessPlatform, "_create_api_client_instance", new_callable=AsyncMock)
async def test_get_service_parameters_maps_all_supported_types(
    mock_create_api_client, mock_exchange_token, platform
):
    mock_exchange_token.return_value = "exchanged-token"

    api_client = MagicMock()
    api_client.get_process_description.return_value = SimpleNamespace(
        inputs={
            "acquired_at": build_input(
                "Acquisition datetime",
                1,
                {"format": "date-time"},
            ),
            "temporal_extent": build_input(
                "Temporal range",
                0,
                {"type": "array", "subtype": "date-interval"},
            ),
            "bbox": build_input(
                "Spatial extent",
                1,
                {"type": "object", "subtype": "bounding-box"},
            ),
            "geometry": build_input(
                "Area of interest",
                0,
                {"format": "geojson"},
            ),
            "enabled": build_input(
                "Boolean flag",
                1,
                {"type": "boolean"},
            ),
            "limit": build_input(
                "Maximum number of items",
                0,
                {"type": "integer"},
            ),
            "threshold": build_input(
                "Threshold value",
                1,
                {"type": "number"},
            ),
            "mode": build_input(
                "Execution mode",
                0,
                {"type": "string", "enum": ["fast", "accurate"]},
            ),
            "bands": build_input(
                "Band list",
                1,
                {"type": "array", "items": {"type": "string"}},
            ),
        }
    )
    mock_create_api_client.return_value = api_client

    result = await platform.get_service_parameters(
        user_token="token",
        details=ServiceDetails(
            endpoint="https://example.com",
            namespace="ns",
            application="my-process",
        ),
    )

    assert result == [
        Parameter(
            name="acquired_at",
            description="Acquisition datetime",
            default=None,
            optional=False,
            type=ParamTypeEnum.DATETIME,
            options=[],
        ),
        Parameter(
            name="temporal_extent",
            description="Temporal range",
            default=None,
            optional=True,
            type=ParamTypeEnum.DATE_INTERVAL,
            options=[],
        ),
        Parameter(
            name="bbox",
            description="Spatial extent",
            default=None,
            optional=False,
            type=ParamTypeEnum.BOUNDING_BOX,
            options=[],
        ),
        Parameter(
            name="geometry",
            description="Area of interest",
            default=None,
            optional=True,
            type=ParamTypeEnum.POLYGON,
            options=[],
        ),
        Parameter(
            name="enabled",
            description="Boolean flag",
            default=None,
            optional=False,
            type=ParamTypeEnum.BOOLEAN,
            options=[],
        ),
        Parameter(
            name="limit",
            description="Maximum number of items",
            default=None,
            optional=True,
            type=ParamTypeEnum.INTEGER,
            options=[],
        ),
        Parameter(
            name="threshold",
            description="Threshold value",
            default=None,
            optional=False,
            type=ParamTypeEnum.DOUBLE,
            options=[],
        ),
        Parameter(
            name="mode",
            description="Execution mode",
            default=None,
            optional=True,
            type=ParamTypeEnum.STRING,
            options=["fast", "accurate"],
        ),
        Parameter(
            name="bands",
            description="Band list",
            default=None,
            optional=False,
            type=ParamTypeEnum.ARRAY_STRING,
            options=[],
        ),
    ]
