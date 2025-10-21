# Getting Started

## Prerequisites

Before running the APEx Dispatch API locally, ensure the following prerequisites are met:

* A working Python environment to install and run the API dependencies.
* A PostgreSQL database to store job-related information.

## Running the API on your local environment

Follow these steps to set up and run the API in your local development environment:

### Install dependencies
Use `pip` to install the required Python packages:

```bash
pip install -r requirements.txt
```

### Set up the database
To set up a PostgreSQL database locally, you can use Docker for convenience and persistence.

#### (Optional) Create a Docker Volume
This step ensures your PostgreSQL data is stored persistently:

```bash
docker volume create local-postgres-data
```

To view the physical location of the volume on your host machine:

```bash
docker volume inspect local-postgres-data
```

#### Start a PostgreSQL Container
Run the following command to start a PostgreSQL instance linked to your volume:

```bash
docker run -d --name postgres -p 5432:5432 \
    -e POSTGRES_USER=testuser \
    -e POSTGRES_PASSWORD=secret \
    -e POSTGRES_DB=testdb \
    -v local-postgres-data:/var/lib/docker/volumes/local-postgres-data \
    postgres:latest
```


### Configure the environment

Create a `.env` file in the root directory of the project and set the necessary environment variables as described in the [Environment Configuration](environment.md) documentation.

### Apply Database Migrations
Ensure your database schema is up-to-date by running:

```bash
alembic upgrade head
```

### Running the API
To start the API, open a new terminal and execute the following:

```bash
uvicorn app.main:app --reload
```

The API will be available at:

* Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Running Tests

Testing is essential to ensure stability and prevent regression issues from affecting the functionality of the API. This project includes a comprehensive suite of tests to validate its core features and maintain code quality.

### Unit Testing

The repository contains an extensive collection of unit tests that cover the main components and functionalities of the codebase. To execute the test suite, run:

```bash
pytest
```

This will automatically discover and run all tests located in the designated test directories.

### Linting
To maintain consistent code quality and enforce best practices, the project uses `flake8` for linting and `mypy` for static type checking. You can run these tools manually with the following commands:

```bash
flake8 app tests
mypy app
```

These checks help identify potential issues early, such as syntax errors, unused imports, and type mismatches, contributing to a more robust and maintainable codebase.