import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_admin
from app.models import Customer
from app.security import hash_password
from app.utils import api_error, api_success

router = APIRouter(dependencies=[Depends(require_admin)])

EXCEL_TEMPLATES_DIR = os.environ.get("EXCEL_TEMPLATES_DIR") or os.path.join(os.getcwd(), "excel_templates")
os.makedirs(EXCEL_TEMPLATES_DIR, exist_ok=True)


class CustomerCreate(BaseModel):
    email: EmailStr
    password: str
    excel_template_config: Optional[dict] = None
    category_rules: Optional[dict] = None


@router.post("/customers")
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    """Admin-only v MVP: zakládá zákazníka a jeho konfiguraci (kategorie, Excel šablona)."""
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
    return api_success({
        "id": customer.id,
        "email": customer.email,
        "excel_template_config": customer.excel_template_config,
        "category_rules": customer.category_rules,
    }, "Customer created successfully.")


@router.get("/customers")
def list_customers(db: Session = Depends(get_db)):
    customers = db.query(Customer).order_by(Customer.id).all()
    return api_success([
        {
            "id": customer.id,
            "email": customer.email,
            "excel_template_config": customer.excel_template_config,
            "category_rules": customer.category_rules,
        }
        for customer in customers
    ], "Customers fetched successfully.")


@router.post("/customers/{customer_id}/template")
async def upload_customer_template(customer_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if customer is None:
        return JSONResponse(status_code=404, content=api_error("Customer not found.", "customer_not_found"))

    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        return JSONResponse(status_code=400, content=api_error("Only Excel templates are allowed (.xlsx, .xls).", "invalid_template"))

    safe_name = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(EXCEL_TEMPLATES_DIR, safe_name)
    content = await file.read()
    with open(file_path, "wb") as target:
        target.write(content)

    customer.excel_template_config = {
        **customer.excel_template_config,
        "template_path": file_path,
        "template_name": file.filename,
    }
    db.commit()
    return api_success({
        "customer_id": customer.id,
        "template_path": file_path,
        "template_name": file.filename,
    }, "Excel template uploaded successfully.")
