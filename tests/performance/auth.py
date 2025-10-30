import os

from dotenv import load_dotenv
import requests

load_dotenv()

URL = os.getenv("KEYCLOAK_HOST")
REALM = os.getenv("KEYCLOAK_REALM")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_PERFORMANCE_ID")
CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_PERFORMANCE_SECRET")


def get_token_client_credentials():
    url = f"https://{URL}/realms/{REALM}/protocol/openid-connect/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    r = requests.post(url, data=data, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]
