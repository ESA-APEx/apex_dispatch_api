# APEx Dispatch API (FastAPI)

This repository contains the implementation of the APEx Upscaling Service API using FastAPI.

## Getting Started: Running the API Locally

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**

   Create a `.env` file and set your environment variables accordingly (e.g., `DATABASE_URL`).

3. **Set up the database:**

   Follow the [Database Setup](#database-setup) instructions below to prepare your local PostgreSQL instance.

4. **Run the FastAPI application:**

   ```bash
   uvicorn app.main:app --reload
   ```

## Running Tests

Execute the test suite using:

```bash
pytest
```

## Database Setup

1. **(Optional) Create a Docker volume to persist PostgreSQL data:**

   ```bash
   docker volume create local-postgres-data
   ```

2. **(Optional) Inspect the volume mount point:**

   ```bash
   docker volume inspect local-postgres-data
   ```

   This shows the physical location of your data on the host machine.

3. **Start a PostgreSQL container linked to the volume:**

   ```bash
   docker run -d --name postgres -p 5432:5432 \
     -e POSTGRES_USER=testuser \
     -e POSTGRES_PASSWORD=secret \
     -e POSTGRES_DB=testdb \
     -v local-postgres-data:/var/lib/docker/volumes/local-postgres-data \
     postgres:latest
   ```

4. **Set your database connection string:**

   Add the following to your `.env.local` (or `.env`) file:

   ```env
   DATABASE_URL=postgresql+psycopg2://testuser:secret@localhost:5432/testdb
   ```

5. **Apply database migrations:**

   Make sure your database schema is up-to-date by running:

   ```bash
   alembic upgrade head
   ```