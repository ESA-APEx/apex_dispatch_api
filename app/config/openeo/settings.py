from enum import Enum
from typing import Optional
from pydantic import BaseModel


class OpenEOBackendConfig(BaseModel):
    client_credentials: Optional[str] = None
    token_provider: Optional[str] = None
    token_prefix: Optional[str] = None


class OpenEOAuthMethod(str, Enum):
    CLIENT_CREDENTIALS = "CLIENT_CREDENTIALS"
    USER_CREDENTIALS = "USER_CREDENTIALS"
