from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel


class AuthMethod(str, Enum):
    CLIENT_CREDENTIALS = "CLIENT_CREDENTIALS"
    USER_CREDENTIALS = "USER_CREDENTIALS"


class TokenExchangeMethod(str, Enum):
    IDENTITY_BROKERING = "identity_brokering"
    TRUSTED_TOKEN_DELEGATION = "trusted_token_delegation"


class BackendAuthConfig(BaseModel):
    auth_method: AuthMethod = AuthMethod.USER_CREDENTIALS
    client_credentials: Optional[str] = None
    token_provider: Optional[str] = None
    token_prefix: Optional[str] = None

    # Values to be set in case of
    # Cross-Domain Federation/Trusted Token Delegation
    exchange_method: Literal[
        TokenExchangeMethod.IDENTITY_BROKERING,
        TokenExchangeMethod.TRUSTED_TOKEN_DELEGATION,
    ] = TokenExchangeMethod.IDENTITY_BROKERING
    token_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    subject_issuer: Optional[str] = None
    audience: Optional[str] = None
