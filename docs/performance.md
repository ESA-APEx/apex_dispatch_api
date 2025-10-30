# Executing Performance Tests

This repository includes tools to execute performance tests for the **APEx Dispatch API**.
Performance testing is useful for analyzing the impact of code changes, database updates, and platform modifications on the system's behavior and responsiveness.

## Prerequisites

Before running the performance tests, ensure the following prerequisites are met:

* **Python environment** (Python 3.10+ recommended)
* **Docker** and **Docker Compose** installed on your system

## Setting Up the Environment

Performance tests require both the API and a database to be running locally. Follow these steps to set up your environment:

1. **Create a `.env` file** in the root of the repository with the following variables:

   * `OPENEO_BACKENDS_PERFORMANCE` → Configuration for the openEO backend authentication. See [configuration guide](./configuration.md#openeo-backend-configuration).
   * `KEYCLOAK_CLIENT_PERFORMANCE_ID` → Client ID used for executing performance tests.
   * `KEYCLOAK_CLIENT_PERFORMANCE_SECRET` → Client secret used for executing performance tests.

2. **Start the services using Docker Compose**:

   ```bash
   docker compose -f docker-compose.perf.yml up -d db
   ```

   Starts a local database instance.

   ```bash
   docker compose -f docker-compose.perf.yml up -d migrate
   ```

   Executes database migrations to ensure all required tables are created.

   ```bash
   docker compose -f docker-compose.perf.yml up -d app
   ```

   Starts the API locally.

> **Tip:** You can check the logs of each service with `docker compose -f docker-compose.perf.yml logs -f <service_name>`.

## Executing Performance Tests

The performance tests are implemented using **[Locust](https://locust.io/)**. Test scenarios are located in `tests/performance/locustfile.py`.

### Running Tests with a Web Dashboard

To execute the performance tests and monitor them in a browser dashboard:

```bash
locust -f tests/performance/locustfile.py -u 10 --host http://localhost:8000 --run-time 1m
```

* `-u 10` → Number of simulated concurrent users
* `--host http://localhost:8000` → URL of the API to test
* `--run-time 1m` → Duration of the test

After starting, open your browser at [http://localhost:8089](http://localhost:8089) to monitor real-time performance metrics, including response times, failure rates, and throughput.

### Running Tests in Headless Mode

To execute tests without a web interface (useful for CI/CD pipelines):

```bash
locust -f tests/performance/locustfile.py -u 10 --host http://localhost:8000 --run-time 1m --headless
```

You can also export the results to a CSV file for further analysis:

```bash
locust -f tests/performance/locustfile.py -u 10 --host http://localhost:8000 --run-time 1m --headless --csv=perf_test_results
```

### Recommended Practices

* Start with a small number of users to validate test scripts before scaling up.
* Combine performance testing with monitoring tools to detect resource bottlenecks.
