from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer()


async def require_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Extract the Bearer token forwarded by the CM handler."""
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return credentials.credentials
