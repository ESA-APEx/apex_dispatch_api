from unittest.mock import patch


@patch("app.routers.health.check_db_status")
def test_health(mock_db_status, client):
    db_status = {"status": "error", "message": "Database connection failed"}
    mock_db_status.return_value = db_status
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": db_status}
