import secrets
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Customer
from app.security import ADMIN_API_KEY, decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)
_admin_key_scheme = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def get_current_customer(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Customer:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")

    customer_id = decode_access_token(credentials.credentials)
    if customer_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Customer no longer exists.")

    return customer


def require_admin(admin_key: Optional[str] = Depends(_admin_key_scheme)) -> None:
    """Chrání admin-only endpointy (zakládání zákazníků, admin registrace).

    V MVP nemá admin žádné vlastní UI/účet - jen sdílený klíč v hlavičce X-Admin-Key.
    """
    if not admin_key or not secrets.compare_digest(admin_key, ADMIN_API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing admin key.")
