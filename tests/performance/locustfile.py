"""
Run locally:
  pip install -r requirements.txt
  locust -f locust.py --headless -u 50 -r 5 --run-time 2m --host http://localhost:8000
"""

import logging
from locust import HttpUser, task, between
from locust.exception import StopUser
from tests.performance.auth import get_token_client_credentials
from tests.performance.utils import random_temporal_extent


class DispatchUser(HttpUser):

    logger = logging.getLogger("user")
    wait_time = between(1.0, 3.0)  # user "think" time

    def on_start(self):
        token = get_token_client_credentials()
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # simple health check at start; stop user if service unreachable
        with self.client.get("/health", name="health", catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"Health check failed: {r.status_code}")
                # stop this virtual user if service down
                raise StopUser()

    @task
    def execute_statistics(self):
        extent = random_temporal_extent(2024)
        payload = {
            "title": "Test Processing Job",
            "label": "openeo",
            "service": {
                "endpoint": "https://openeo.vito.be",
                "application": "https://openeo.vito.be/openeo/1.2/processes/"
                + "u:ff5c137fbbbf409d14a99875b97109874058056a9a02193e6fde8217d2f1f3e8@egi.eu/"
                + "timeseries_graph",
            },
            "format": "json",
            "parameters": {
                "spatial_extent": {
                    "type": "Point",
                    "coordinates": [5.196363779293476, 51.25007554845948],
                },
                "collection": "CGLS_NDVI300_V2_GLOBAL",
                "band": "NDVI",
                "temporal_extent": extent,
            },
        }
        self.logger.info(f"Requesting statistics for extent: {extent}")
        self.client.post(
            "/sync_jobs",
            json=payload,
            name="statistics",
            timeout=30,
            headers=self.headers,
        )
