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

    # Values to be set in case of 
    # Cross-Domain Federation/Trusted Token Delegation
    token_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    subject_issuer: Optional[str] = None
    audience: Optional[str] = None
