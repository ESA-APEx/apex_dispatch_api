from unittest.mock import patch

import pytest

import app.platforms.dispatcher as dispatcher
from app.platforms.base import BaseProcessingPlatform
from app.schemas.enum import ProcessTypeEnum, ProcessingStatusEnum
from app.schemas.unit_job import ProcessingJobSummary

from stac_pydantic import Collection

from tests.conftest import fake_parameter_result, fake_sync_response


class DummyPlatform(BaseProcessingPlatform):
    def __init__(self, result: Collection = None):
        super().__init__()
        self.fake_result = result

    def execute_job(
        self, title: str, details: dict, parameters: dict
    ) -> ProcessingJobSummary:
        return ProcessingJobSummary(id="dummy-job-id", title=title, status="created")

    def execute_synchronous_job(self, user_token, title, details, parameters, format):
        return fake_sync_response()

    def get_job_status(self, job_id, details):
        return ProcessingStatusEnum.FINISHED

    def get_job_results(self, job_id, details):
        return self.fake_result

    def get_service_parameters(self, user_token, details):
        return fake_parameter_result()


@pytest.fixture(autouse=True)
def clear_registry():
    """Ensure PROCESSING_PLATFORMS is clean before each test."""
    dispatcher.PROCESSING_PLATFORMS.clear()
    yield
    dispatcher.PROCESSING_PLATFORMS.clear()


def test_register_processing_platform():
    dispatcher.register_platform(ProcessTypeEnum.OPENEO)(DummyPlatform)
    assert dispatcher.PROCESSING_PLATFORMS[ProcessTypeEnum.OPENEO] is DummyPlatform


def test_get_processing_platform_success():
    dispatcher.PROCESSING_PLATFORMS[ProcessTypeEnum.OPENEO] = DummyPlatform
    instance = dispatcher.get_processing_platform(ProcessTypeEnum.OPENEO)
    assert isinstance(instance, DummyPlatform)


def test_get_processing_platform_unsupported():
    with pytest.raises(ValueError, match="Unsupported service type"):
        dispatcher.get_processing_platform(ProcessTypeEnum.OPENEO)


@patch("app.platforms.dispatcher.importlib.import_module")
@patch("app.platforms.dispatcher.pkgutil.iter_modules")
def test_load_processing_platforms(mock_iter_modules, mock_import_module):
    # Simulate two modules found in the implementations package
    mock_iter_modules.return_value = [
        (None, "mod1", False),
        (None, "mod2", False),
    ]

    dispatcher.load_processing_platforms()

    mock_import_module.assert_any_call("app.platforms.implementations.mod1")
    mock_import_module.assert_any_call("app.platforms.implementations.mod2")
    assert mock_import_module.call_count == 2


@patch("app.platforms.dispatcher.pkgutil.iter_modules")
def test_load_processing_platforms_no_modules(mock_iter_modules):
    mock_iter_modules.return_value = []
    # Should not raise, just do nothing
    dispatcher.load_processing_platforms()
