# APEx Dispatch API (FastAPI)
Implementation of the APEx Upscaling Service API


## Running the API locally

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set up your environment variables in a `.env.local` file
3. Run the FastAPI application:
   ```bash
   uvicorn app.main:app --reload
   ```

## Running Tests

To run the tests, use the following command:
```bash
pytest
```