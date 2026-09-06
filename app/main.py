import asyncio
import logging
import os

from fastapi import FastAPI
from sqlalchemy import text

from app.db import SessionLocal
from app.routers import auth, customers, invoices, me, upload
from app.services.pipeline import process_invoice, reap_stuck_invoices

logger = logging.getLogger(__name__)

WATCHDOG_INTERVAL_SECONDS = int(os.environ.get("WATCHDOG_INTERVAL_SECONDS", "120"))

app = FastAPI(title="Invoice OCR Tool")

app.include_router(auth.router)
app.include_router(customers.router)
app.include_router(upload.router)
app.include_router(invoices.router)
app.include_router(me.router)


async def _watchdog_loop() -> None:
    """Periodicky odchytává faktury zaseklé v `processing` (viz pipeline.py) -
    náhrada za pořádnou frontu úloh (Celery/RQ), zatím přiměřená velikosti
    appky (jeden uvicorn proces). Běží jako background task appky samotné,
    ne jako samostatná služba, aby fungovala i bez další infrastruktury."""
    while True:
        try:
            requeued_ids = await asyncio.to_thread(reap_stuck_invoices)
            for invoice_id in requeued_ids:
                await asyncio.to_thread(process_invoice, invoice_id)
        except Exception:
            logger.exception("Watchdog: iterace selhala, zkusí to znovu za %s s.", WATCHDOG_INTERVAL_SECONDS)
        await asyncio.sleep(WATCHDOG_INTERVAL_SECONDS)


@app.on_event("startup")
async def _start_watchdog() -> None:
    asyncio.create_task(_watchdog_loop())


@app.get("/health")
def health():
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db_ok = True
        finally:
            db.close()
    except Exception:
        logger.exception("Health check: spojení na databázi selhalo.")
        db_ok = False

    return {
        "success": db_ok,
        "data": {"status": "ok" if db_ok else "degraded", "database": db_ok},
        "message": "Health check passed." if db_ok else "Database connection failed.",
    }
