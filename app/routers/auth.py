from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_admin
from app.models import Customer
from app.rate_limit import client_ip, record_failed_attempt, reset_attempts, seconds_until_retry
from app.security import create_access_token, hash_password, verify_password
from app.utils import api_error, api_success

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    excel_template_config: Optional[dict] = None
    category_rules: Optional[dict] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", dependencies=[Depends(require_admin)])
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Admin-only v MVP: zakládá zákazníka. Bez veřejné self-service registrace."""
    if len(payload.password) < 8:
        return JSONResponse(status_code=400, content=api_error("Password must be at least 8 characters long.", "weak_password"))

    existing = db.query(Customer).filter(Customer.email == payload.email).first()
    if existing:
        return JSONResponse(status_code=409, content=api_error(f"Customer with email '{payload.email}' already exists.", "customer_exists"))

    customer = Customer(
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        excel_template_config=payload.excel_template_config or {},
        category_rules=payload.category_rules or {},
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    token = create_access_token(customer.id)
    return api_success({
        "access_token": token,
        "token_type": "bearer",
        "customer": {"id": customer.id, "email": customer.email},
    }, "Customer registered successfully.")


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None)

    retry_after = seconds_until_retry(ip, payload.email)
    if retry_after is not None:
        return JSONResponse(
            status_code=429,
            content=api_error("Too many login attempts. Please try again later.", "rate_limited"),
            headers={"Retry-After": str(retry_after)},
        )

    customer = db.query(Customer).filter(Customer.email == payload.email).first()
    if customer is None or not verify_password(payload.password, customer.password_hash):
        record_failed_attempt(ip, payload.email)
        return JSONResponse(status_code=401, content=api_error("Invalid email or password.", "invalid_credentials"))

    reset_attempts(ip, payload.email)
    token = create_access_token(customer.id)
    return api_success({
        "access_token": token,
        "token_type": "bearer",
        "customer": {"id": customer.id, "email": customer.email},
    }, "Login successful.")
