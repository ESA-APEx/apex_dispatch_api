import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)


# @pytest.fixture(autouse=True)
# def disable_auth(monkeypatch):
#     # Replace auth.get_current_user dependency with a stub for tests
#     from app import auth

#     monkeypatch.setattr(auth, "get_current_user", lambda: {"sub": "test-user"})
