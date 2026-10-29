"""Offline security tests; all GEP feature changes remain inside this package."""
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from http_apis_problems_detail.fastapi import (
    ProblemRegistryException, problem_registry_exception_handler,
)

from app.config.settings import settings
from app.platforms.implementations.gep import auth
from app.platforms.implementations.gep import router as routes
from app.platforms.implementations.gep.settings import get_callback_backends
from app.platforms.implementations.gep.subscriber import CALLBACK_PREFIX
from app.schemas.enum import ProcessingStatusEnum

ISSUER = "https://iam.example.test/realms/callbacks"
ENDPOINT = "https://mate.example.test"


@pytest.fixture
def harness(monkeypatch):
    backend = dict(token_provider="terradue", callback_issuer=ISSUER,
                   callback_audience="apex-dispatch-api",
                   callback_clients=["mate-api-callbacks"])
    monkeypatch.setattr(settings, "backends", json.dumps({ENDPOINT: backend}))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks = MagicMock()
    jwks.get_signing_key_from_jwt.return_value.key = key.public_key()
    factory = MagicMock(return_value=jwks)
    monkeypatch.setattr(auth, "_callback_jwks_client", factory)
    job = SimpleNamespace(id=1, status=ProcessingStatusEnum.RUNNING,
                          service=json.dumps({"endpoint": ENDPOINT}))
    lookup = MagicMock(return_value=job)
    update = MagicMock()
    monkeypatch.setattr(routes, "get_gep_job", lookup)
    monkeypatch.setattr(routes, "apply_job_status", update)
    api = FastAPI()
    api.include_router(routes.router)
    api.add_exception_handler(ProblemRegistryException, problem_registry_exception_handler)
    api.dependency_overrides[routes.get_db] = lambda: MagicMock()

    def token(**changes):
        claims = dict(iss=ISSUER, aud="apex-dispatch-api", azp="mate-api-callbacks",
                      exp=int(time.time()) + 300)
        claims.update(changes)
        return jwt.encode({k: v for k, v in claims.items() if v is not None},
                          key, algorithm="RS256", headers={"kid": "test"})

    with TestClient(api) as client:
        yield SimpleNamespace(client=client, token=token, lookup=lookup, update=update,
                              job=job, factory=factory, backend=backend, api=api)


def post(h, endpoint="success", token=None):
    event_type = {"success": "piped", "inProgress": "staged", "failed": "failed"}[endpoint]
    payload = dict(source="terradue:apex:test", subject="default:uid:job-123",
                   partitionkey="part-1", type=event_type,
                   data=dict(namespace="default", process_id="test-proc", job_id="job-123",
                             entries={}, outputs={}, usage={}))
    return h.client.post(CALLBACK_PREFIX + "/" + endpoint, json=payload,
                         headers={} if token is None else {"Authorization": token})


@pytest.mark.parametrize("endpoint", ["success", "inProgress", "failed"])
@pytest.mark.parametrize("scenario,expected", [
    ("valid", 200), ("missing", 401), ("basic", 401), ("malformed", 401),
    ("expired", 401), ("issuer", 401), ("audience", 401), ("no_exp", 401),
    ("no_aud", 401), ("no_iss", 401), ("future_nbf", 401), ("future_iat", 401),
    ("client", 403), ("no_azp", 403), ("other_job", 403), ("slash", 200),
    ("bad_signature", 401), ("jwks_failure", 401), ("algorithm", 401),
])
def test_callback_security(harness, endpoint, scenario, expected):
    h = harness
    changes = {"expired": {"exp": 1}, "issuer": {"iss": "https://unknown.test"},
               "audience": {"aud": "other"}, "no_exp": {"exp": None},
               "no_aud": {"aud": None}, "no_iss": {"iss": None},
               "future_nbf": {"nbf": 9999999999}, "future_iat": {"iat": 9999999999},
               "client": {"azp": "other"}, "no_azp": {"azp": None}}
    token = "Bearer " + h.token(**changes.get(scenario, {}))
    if scenario == "missing":
        token = None
    elif scenario == "basic":
        token = "Basic abc"
    elif scenario == "malformed":
        token = "Bearer invalid"
    elif scenario in ("other_job", "slash"):
        target = "https://other.test" if scenario == "other_job" else ENDPOINT + "/"
        h.job.service = json.dumps({"endpoint": target})
    elif scenario == "bad_signature":
        h.factory.return_value.get_signing_key_from_jwt.return_value.key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048).public_key()
    elif scenario == "jwks_failure":
        h.factory.return_value.get_signing_key_from_jwt.side_effect = (
            jwt.PyJWKClientConnectionError("offline")
        )
    elif scenario == "algorithm":
        token = "Bearer " + jwt.encode({"iss": ISSUER}, "x" * 32, algorithm="HS256")
    response = post(h, endpoint, token)
    assert response.status_code == expected, response.text
    if expected == 200:
        h.update.assert_called_once()
    else:
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["status"] == expected
        assert response.json()["instance"].endswith(CALLBACK_PREFIX + "/" + endpoint)
        h.update.assert_not_called()
    if expected == 401:
        assert response.headers["www-authenticate"] == "Bearer"
        h.lookup.assert_not_called()
    if scenario in ("issuer", "no_iss"):
        h.factory.assert_not_called()


@pytest.mark.parametrize("other_policy", ["client", "audience", "disabled"])
def test_shared_issuer_isolation(harness, monkeypatch, other_policy):
    h = harness
    other = dict(h.backend)
    other.update({"client": {"callback_clients": ["other"]},
                  "audience": {"callback_audience": "other"},
                  "disabled": {"callback_clients": []}}[other_policy])
    backends_config = {ENDPOINT: h.backend, "https://other.test": other}
    monkeypatch.setattr(settings, "backends", json.dumps(backends_config))
    h.job.service = json.dumps({"endpoint": "https://other.test"})
    assert post(h, token="Bearer " + h.token()).status_code == 403
    h.update.assert_not_called()


def test_raw_backends_retains_local_fields(harness):
    # Shared config deliberately remains unchanged and drops these extra fields.
    from app.config.schemas import BackendAuthConfig
    assert not hasattr(BackendAuthConfig(**harness.backend), "callback_issuer")
    assert get_callback_backends()[ENDPOINT].callback_issuer == ISSUER


@pytest.mark.parametrize("raw", ["", "{}"])
def test_no_config_fails_closed(harness, monkeypatch, raw):
    monkeypatch.setattr(settings, "backends", raw)
    assert post(harness, token="Bearer " + harness.token()).status_code == 401
    harness.factory.assert_not_called()


@pytest.mark.parametrize(
    "endpoint,expected", [("success", 404), ("failed", 404), ("inProgress", 200)]
)
def test_unknown_job(harness, endpoint, expected):
    harness.lookup.return_value = None
    assert post(harness, endpoint, "Bearer " + harness.token()).status_code == expected
    harness.update.assert_not_called()


def test_transition_failure(harness):
    harness.update.side_effect = routes.InvalidJobTransition("Invalid transition")
    assert post(harness, token="Bearer " + harness.token()).status_code == 422


def test_openapi(harness):
    schema = harness.api.openapi()
    for endpoint in ("success", "inProgress", "failed"):
        operation = schema["paths"][CALLBACK_PREFIX + "/" + endpoint]["post"]
        assert {"GepCallbackBearer": []} in operation["security"]
        for code in ("401", "403"):
            assert "application/problem+json" in operation["responses"][code]["content"]
