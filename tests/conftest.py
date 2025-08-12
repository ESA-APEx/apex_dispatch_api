from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_db_session():
    # A simple mock DB session object
    return MagicMock(spec=Session)


# @pytest.fixture(autouse=True)
# def disable_auth(monkeypatch):
#     # Replace auth.get_current_user dependency with a stub for tests
#     from app import auth

#     monkeypatch.setattr(auth, "get_current_user", lambda: {"sub": "test-user"})
