import os
import uuid
from datetime import datetime, timedelta
from typing import List

import magic
from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy import func
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

# Přípona sama o sobě nic nedokazuje - "účtenka.pdf", která je ve skutečnosti
# libovolný jiný soubor, projde kontrolou přípony bez problému. Skutečný typ
# obsahu (magic bytes) ověřujeme přes libmagic, ne přes to, co si klient řekne.
ALLOWED_MIME_BY_EXTENSION = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".tif": {"image/tiff"},
    ".tiff": {"image/tiff"},
    ".bmp": {"image/bmp", "image/x-ms-bmp", "image/x-bmp"},
    ".webp": {"image/webp"},
}

# Ochrana proti zaplnění disku/přehlcení OCR fronty jedním účtem - žádný reálný
# řemeslník/mikrofirma nenahraje stovky dokladů za den, i při jednorázovém
# hromadném importu historie by tohle mělo stačit s rezervou.
MAX_UPLOADS_PER_DAY = int(os.environ.get("MAX_UPLOADS_PER_DAY", "300"))


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

    cutoff = datetime.utcnow() - timedelta(hours=24)
    uploads_last_24h = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.customer_id == current_customer.id, Invoice.created_at >= cutoff)
        .scalar()
        or 0
    )

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

        if uploads_last_24h >= MAX_UPLOADS_PER_DAY:
            created.append({
                "original_filename": file.filename,
                "status": "rejected",
                "reason": f"Daily upload limit ({MAX_UPLOADS_PER_DAY} files) reached, try again tomorrow.",
            })
            continue

        contents = await file.read()

        detected_mime = magic.from_buffer(contents, mime=True)
        if detected_mime not in ALLOWED_MIME_BY_EXTENSION.get(extension, set()):
            created.append({
                "original_filename": file.filename,
                "status": "rejected",
                "reason": f"File content does not match its extension (detected: {detected_mime}).",
            })
            continue

        # os.path.basename navíc k UUID prefixu - v praxi šlo path traversal
        # přes tenhle název už dřív vyzkoušet a nešlo (UUID prefix bez oddělovače
        # rozbije první segment cesty na neexistující adresář), ale spoléhat na
        # tuhle náhodu je křehké - basename ho eliminuje najisto.
        safe_name = f"{uuid.uuid4()}_{os.path.basename(file.filename)}"
        file_path = os.path.join(UPLOAD_DIR, safe_name)
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
        uploads_last_24h += 1

        created.append({
            "invoice_id": invoice.id,
            "original_filename": invoice.original_filename,
            "status": invoice.status,
        })

    return api_success(created, "Files uploaded, processing started in the background.")
