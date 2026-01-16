from enum import Enum
from typing import Optional
from pydantic import BaseModel


class AuthMethod(str, Enum):
    CLIENT_CREDENTIALS = "CLIENT_CREDENTIALS"
    USER_CREDENTIALS = "USER_CREDENTIALS"


class BackendAuthConfig(BaseModel):
    auth_method: AuthMethod = AuthMethod.USER_CREDENTIALS
    client_credentials: Optional[str] = None
    token_provider: Optional[str] = None
    token_prefix: Optional[str] = None
