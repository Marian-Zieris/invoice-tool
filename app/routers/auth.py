from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_admin
from app.models import Customer
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
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.email == payload.email).first()
    if customer is None or not verify_password(payload.password, customer.password_hash):
        return JSONResponse(status_code=401, content=api_error("Invalid email or password.", "invalid_credentials"))

    token = create_access_token(customer.id)
    return api_success({
        "access_token": token,
        "token_type": "bearer",
        "customer": {"id": customer.id, "email": customer.email},
    }, "Login successful.")
