import os
import uuid
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_customer
from app.models import Customer, Invoice
from app.services.pipeline import process_invoice
from app.utils import api_success

router = APIRouter()

UPLOAD_DIR = os.environ.get("UPLOAD_DIR") or (
    "/app/uploads" if os.path.isdir("/app") and os.access("/app", os.W_OK) else os.path.join(os.getcwd(), "uploads")
)
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


@router.post("/invoices/upload")
async def upload_invoices(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    """Multi-file upload. Soubory se hned uloží a založí se Invoice(status=uploaded),
    request se vrací okamžitě - reálné OCR/LLM zpracování běží na pozadí."""
    created = []

    for file in files:
        if not file.filename:
            continue

        extension = os.path.splitext(file.filename)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            created.append({
                "original_filename": file.filename,
                "status": "rejected",
                "reason": f"Unsupported file type: {extension or 'unknown'}",
            })
            continue

        safe_name = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, safe_name)
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        invoice = Invoice(
            customer_id=current_customer.id,
            original_filename=file.filename,
            file_path=file_path,
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)

        background_tasks.add_task(process_invoice, invoice.id)

        created.append({
            "invoice_id": invoice.id,
            "original_filename": invoice.original_filename,
            "status": invoice.status,
        })

    return api_success(created, "Files uploaded, processing started in the background.")
