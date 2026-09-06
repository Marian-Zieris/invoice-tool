import logging
import os
from datetime import date, datetime, timedelta
from typing import List, Optional

from app.db import SessionLocal
from app.models import Invoice, InvoiceStatus, LineItem
from app.services.llm import ExtractionError, extract_invoice_data
from app.services.ocr import extract_text_from_file

logger = logging.getLogger(__name__)

_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y")

# Kolik minut smí faktura sedět v "processing", než ji watchdog (viz
# reap_stuck_invoices, spouští se z app/main.py) považuje za zaseklou - typicky
# pád procesu nebo výpadek sítě uprostřed OCR/LLM volání, po kterém by jinak
# zůstala ve zpracování navždy (BackgroundTasks nemají žádný vlastní timeout).
STUCK_PROCESSING_MINUTES = int(os.environ.get("STUCK_PROCESSING_MINUTES", "10"))
MAX_PROCESSING_RETRIES = int(os.environ.get("MAX_PROCESSING_RETRIES", "2"))


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def process_invoice(invoice_id: int) -> None:
    """Kompletní zpracovatelská pipeline pro jednu fakturu, spouští se jako background task.

    Žádný krok tiše neselže - chyby jsou vždy vidět v Invoice.status.
    Otevírá si vlastní DB session, protože běží mimo request lifecycle.
    """
    db = SessionLocal()
    try:
        invoice = db.get(Invoice, invoice_id)
        if invoice is None:
            logger.error("process_invoice: invoice %s not found", invoice_id)
            return

        invoice.status = InvoiceStatus.PROCESSING.value
        invoice.processing_started_at = datetime.utcnow()
        db.commit()

        try:
            raw_text = extract_text_from_file(invoice.file_path)
        except Exception:
            logger.exception("OCR raised an exception for invoice %s", invoice_id)
            invoice.status = InvoiceStatus.OCR_FAILED.value
            db.commit()
            return

        if not raw_text.strip():
            invoice.status = InvoiceStatus.OCR_FAILED.value
            db.commit()
            return

        invoice.raw_ocr_text = raw_text
        db.commit()

        customer = invoice.customer
        try:
            extracted = extract_invoice_data(raw_text, customer.category_rules if customer else None)
        except ExtractionError:
            logger.exception("LLM extraction failed for invoice %s", invoice_id)
            invoice.status = InvoiceStatus.EXTRACTION_FAILED.value
            db.commit()
            return

        invoice.supplier_name = extracted.supplier_name
        invoice.invoice_date = _parse_date(extracted.invoice_date)
        invoice.currency = extracted.currency or "CZK"
        invoice.currency_confidence = extracted.currency_confidence

        for item in extracted.line_items:
            db.add(LineItem(
                invoice_id=invoice.id,
                description=item.description,
                category=item.category,
                amount=item.amount,
                confidence_score=item.confidence_score,
                supplier_name=invoice.supplier_name,
                invoice_date=invoice.invoice_date,
                amount_without_vat=item.amount_without_vat,
                vat_rate=item.vat_rate,
            ))

        # Celkova castka je VZDY soucet skutecne vytezenych polozek, ne cislo, ktere LLM
        # precetlo z radku "Celkem" na dokladu - jinak by fakturu s chybejicimi polozkami
        # (viz extraction_warning nize) klidne ukazovala jako "kompletni" s cislem, ktere
        # neodpovida tomu, co je v tabulce videt a jde zkontrolovat.
        items_sum = round(sum(item.amount for item in extracted.line_items), 2)
        warning = extracted.extraction_warning
        if extracted.line_items:
            invoice.total_amount = items_sum
            if extracted.total_amount is not None and abs(items_sum - extracted.total_amount) > 1.0:
                mismatch_note = (
                    f"Součet položek ({items_sum:.2f}) neodpovídá součtu uvedenému na dokladu "
                    f"({extracted.total_amount:.2f}) - doklad pravděpodobně obsahuje další nepřečtené položky."
                )
                warning = f"{warning} {mismatch_note}" if warning else mismatch_note
        else:
            # Nic se nevytezilo jako polozka, ale LLM aspon precetlo celkovou castku -
            # lepsi nez 0/None, i kdyz to neni rozepsatelne na jednotlive radky.
            invoice.total_amount = extracted.total_amount

        invoice.extraction_warning = warning

        invoice.status = InvoiceStatus.NEEDS_REVIEW.value
        db.commit()
    finally:
        db.close()


def reap_stuck_invoices() -> List[int]:
    """Najde faktury zaseklé v `processing` déle než STUCK_PROCESSING_MINUTES
    a buď je vrátí zpět ke zpracování (do MAX_PROCESSING_RETRIES pokusů), nebo
    je po vyčerpání pokusů označí jako `ocr_failed` - nikdy je nenechá viset
    v `processing` navždy beze změny. Vrací ID faktur, které je potřeba znovu
    poslat do process_invoice (volající strana, viz app/main.py, to udělá mimo
    tuhle DB session).
    """
    cutoff = datetime.utcnow() - timedelta(minutes=STUCK_PROCESSING_MINUTES)
    db = SessionLocal()
    requeued: List[int] = []
    try:
        stuck = (
            db.query(Invoice)
            .filter(Invoice.status == InvoiceStatus.PROCESSING.value)
            .filter(Invoice.processing_started_at.isnot(None))
            .filter(Invoice.processing_started_at < cutoff)
            .all()
        )
        for invoice in stuck:
            if invoice.retry_count >= MAX_PROCESSING_RETRIES:
                logger.error(
                    "Invoice %s stuck in processing since %s after %s retries - giving up.",
                    invoice.id, invoice.processing_started_at, invoice.retry_count,
                )
                invoice.status = InvoiceStatus.OCR_FAILED.value
            else:
                logger.warning(
                    "Invoice %s stuck in processing since %s - retrying (%s/%s).",
                    invoice.id, invoice.processing_started_at, invoice.retry_count + 1, MAX_PROCESSING_RETRIES,
                )
                invoice.status = InvoiceStatus.UPLOADED.value
                invoice.retry_count += 1
                requeued.append(invoice.id)
        db.commit()
    finally:
        db.close()
    return requeued
