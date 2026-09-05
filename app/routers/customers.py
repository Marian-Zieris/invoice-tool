import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_admin
from app.models import Customer
from app.security import hash_password
from app.services.exporter import DEFAULT_COLUMNS
from app.utils import api_error, api_success

router = APIRouter(dependencies=[Depends(require_admin)])

EXCEL_TEMPLATES_DIR = os.environ.get("EXCEL_TEMPLATES_DIR") or os.path.join(os.getcwd(), "excel_templates")
os.makedirs(EXCEL_TEMPLATES_DIR, exist_ok=True)


class CustomerCreate(BaseModel):
    email: EmailStr
    password: str
    excel_template_config: Optional[dict] = None
    category_rules: Optional[dict] = None


class CustomerCategoriesUpdate(BaseModel):
    categories: List[str] = Field(min_length=1)


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


@router.patch("/customers/{customer_id}")
def update_customer_categories(customer_id: int, payload: CustomerCategoriesUpdate, db: Session = Depends(get_db)):
    """Umožní upravit seznam kategorií i po založení účtu - dřív šly nastavit jen jednou při create_customer."""
    customer = db.get(Customer, customer_id)
    if customer is None:
        return JSONResponse(status_code=404, content=api_error("Customer not found.", "customer_not_found"))

    customer.category_rules = {**customer.category_rules, "categories": payload.categories}
    db.commit()
    db.refresh(customer)
    return api_success({
        "id": customer.id,
        "email": customer.email,
        "excel_template_config": customer.excel_template_config,
        "category_rules": customer.category_rules,
    }, "Customer categories updated successfully.")


@router.delete("/customers/{customer_id}")
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    """Smaže účet zákazníka i všechny jeho faktury/položky (cascade, viz models.py) a jejich
    nahrané soubory z disku - nevratná operace, ale admin ji potřebuje na úklid testovacích
    nebo omylem založených účtů."""
    customer = db.get(Customer, customer_id)
    if customer is None:
        return JSONResponse(status_code=404, content=api_error("Customer not found.", "customer_not_found"))

    file_paths = [invoice.file_path for invoice in customer.invoices if invoice.file_path]
    db.delete(customer)
    db.commit()

    for file_path in file_paths:
        try:
            os.remove(file_path)
        except OSError:
            pass

    return api_success(None, "Customer deleted successfully.")


@router.post("/customers/{customer_id}/template")
async def upload_customer_template(
    customer_id: int,
    file: Optional[UploadFile] = File(None),
    sheet_name: Optional[str] = Form(None),
    start_row: Optional[int] = Form(None),
    columns: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Nahraje/aktualizuje Excel šablonu a volitelně nastaví, jak se do ní má exportér mapovat.

    `columns` je čárkou oddělený seznam interních klíčů (viz exporter.DEFAULT_COLUMNS),
    v pořadí, v jakém mají jít do sloupců šablony počínaje `start_row`. Bez něj export
    použije výchozí sadu sloupců - což u šablony s jiným rozvržením typicky nedává smysl,
    proto to admin musí umět nastavit tady, ne jen nahrát soubor naslepo.

    `file` je volitelný, aby šlo upravit jen mapování (sheet_name/start_row/columns) beze
    změny už nahraného souboru - vyžadovat ho vždy by nutilo znovu nahrávat identický
    soubor při každé úpravě konfigurace.
    """
    customer = db.get(Customer, customer_id)
    if customer is None:
        return JSONResponse(status_code=404, content=api_error("Customer not found.", "customer_not_found"))

    config_update: dict = {}

    if file is not None:
        if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
            return JSONResponse(status_code=400, content=api_error("Only Excel templates are allowed (.xlsx, .xls).", "invalid_template"))

        safe_name = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(EXCEL_TEMPLATES_DIR, safe_name)
        content = await file.read()
        with open(file_path, "wb") as target:
            target.write(content)

        config_update["template_path"] = file_path
        config_update["template_name"] = file.filename
    elif not customer.excel_template_config.get("template_path"):
        return JSONResponse(status_code=400, content=api_error("No template file provided and customer has none yet.", "template_required"))

    if sheet_name:
        config_update["sheet_name"] = sheet_name
    if start_row is not None:
        config_update["start_row"] = start_row
    if columns:
        column_keys = [key.strip() for key in columns.split(",") if key.strip()]
        if column_keys:
            config_update["columns"] = column_keys
            config_update["headers"] = [DEFAULT_COLUMNS.get(key, key) for key in column_keys]

    customer.excel_template_config = {**customer.excel_template_config, **config_update}
    db.commit()
    db.refresh(customer)
    return api_success({
        "customer_id": customer.id,
        "excel_template_config": customer.excel_template_config,
    }, "Excel template uploaded successfully.")
