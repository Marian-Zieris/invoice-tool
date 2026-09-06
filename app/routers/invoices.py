import os
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_customer
from app.models import Customer, Invoice, InvoiceStatus, LineItem
from app.services.exporter import export_invoices_to_excel
from app.utils import api_error, api_success

router = APIRouter()


class LineItemUpdate(BaseModel):
    description: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    amount_without_vat: Optional[float] = None
    vat_rate: Optional[float] = None


class InvoiceUpdate(BaseModel):
    # total_amount se sem záměrně nedává - je to vždy odvozená hodnota (součet položek,
    # viz pipeline.py a update_line_item níže), ruční přepis by ji jen znovu rozjel od
    # skutečných dat.
    supplier_name: Optional[str] = None
    invoice_date: Optional[date] = None
    currency: Optional[str] = None


class ExportRequest(BaseModel):
    invoice_ids: List[int] = Field(min_length=1)


class MergeRequest(BaseModel):
    invoice_ids: List[int] = Field(min_length=2)


def _line_item_payload(item: LineItem) -> dict:
    return {
        "id": item.id,
        "invoice_id": item.invoice_id,
        "description": item.description,
        "category": item.category,
        "amount": item.amount,
        "confidence_score": item.confidence_score,
        "is_corrected": item.is_corrected,
        "supplier_name": item.supplier_name,
        "invoice_date": item.invoice_date.isoformat() if item.invoice_date else None,
        "amount_without_vat": item.amount_without_vat,
        "vat_rate": item.vat_rate,
    }


def _invoice_summary_payload(invoice: Invoice) -> dict:
    return {
        "id": invoice.id,
        "original_filename": invoice.original_filename,
        "status": invoice.status,
        "supplier_name": invoice.supplier_name,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "total_amount": invoice.total_amount,
        "currency": invoice.currency,
        "currency_confidence": invoice.currency_confidence,
        "created_at": invoice.created_at.isoformat(),
        "extraction_warning": invoice.extraction_warning,
    }


@router.get("/invoices")
def list_invoices(db: Session = Depends(get_db), current_customer: Customer = Depends(get_current_customer)):
    invoices = (
        db.query(Invoice)
        .filter(Invoice.customer_id == current_customer.id)
        .order_by(Invoice.created_at.desc())
        .all()
    )
    return api_success([_invoice_summary_payload(invoice) for invoice in invoices], "Invoices fetched successfully.")


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, db: Session = Depends(get_db), current_customer: Customer = Depends(get_current_customer)):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.customer_id != current_customer.id:
        return JSONResponse(status_code=404, content=api_error("Invoice not found.", "invoice_not_found"))

    payload = _invoice_summary_payload(invoice)
    payload["raw_ocr_text"] = invoice.raw_ocr_text or ""
    return api_success(payload, "Invoice fetched successfully.")


@router.patch("/invoices/{invoice_id}")
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    """Ruční oprava vytěžených hlavičkových údajů faktury (dodavatel, datum, částka, měna).

    Stejný princip jako PATCH /items/{id}: LLM extrakce se může splést nebo si nebýt jistá
    (typicky měna u cizojazyčného dokladu) - tohle je jediný způsob, jak takovou hodnotu
    zákazník může opravit, protože žádná z těchto hodnot se jinak přepsat nedá.
    """
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.customer_id != current_customer.id:
        return JSONResponse(status_code=404, content=api_error("Invoice not found.", "invoice_not_found"))

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(invoice, field, value)

    if "currency" in changes:
        # Zákazník měnu ručně potvrdil/opravil - nízká LLM jistota už dál
        # neplatí, jinak by se varování v UI zobrazovalo dál i po opravě.
        invoice.currency_confidence = 1.0

    if changes and invoice.status == InvoiceStatus.NEEDS_REVIEW.value:
        invoice.status = InvoiceStatus.REVIEWED.value

    db.commit()
    db.refresh(invoice)

    result = _invoice_summary_payload(invoice)
    result["raw_ocr_text"] = invoice.raw_ocr_text or ""
    return api_success(result, "Invoice updated successfully.")


@router.post("/invoices/{invoice_id}/confirm")
def confirm_invoice(invoice_id: int, db: Session = Depends(get_db), current_customer: Customer = Depends(get_current_customer)):
    """Ruční potvrzení "vypadá to dobře, nic neměním" - bez tohohle neměl
    zákazník jak fakturu označit jako zkontrolovanou, pokud v ní nic neopravoval
    (status se jinak posouvá na `reviewed` jen jako vedlejší efekt PATCH úpravy)."""
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.customer_id != current_customer.id:
        return JSONResponse(status_code=404, content=api_error("Invoice not found.", "invoice_not_found"))

    if invoice.status != InvoiceStatus.NEEDS_REVIEW.value:
        return JSONResponse(
            status_code=400,
            content=api_error("Only invoices awaiting review can be confirmed.", "invalid_status"),
        )

    invoice.status = InvoiceStatus.REVIEWED.value
    db.commit()
    db.refresh(invoice)

    result = _invoice_summary_payload(invoice)
    result["raw_ocr_text"] = invoice.raw_ocr_text or ""
    return api_success(result, "Invoice confirmed as reviewed.")


@router.delete("/invoices/{invoice_id}")
def delete_invoice(invoice_id: int, db: Session = Depends(get_db), current_customer: Customer = Depends(get_current_customer)):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.customer_id != current_customer.id:
        return JSONResponse(status_code=404, content=api_error("Invoice not found.", "invoice_not_found"))

    file_path = invoice.file_path
    db.delete(invoice)
    db.commit()

    if file_path:
        try:
            os.remove(file_path)
        except OSError:
            pass

    return api_success(None, "Invoice deleted successfully.")


@router.get("/invoices/{invoice_id}/items")
def list_invoice_items(invoice_id: int, db: Session = Depends(get_db), current_customer: Customer = Depends(get_current_customer)):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.customer_id != current_customer.id:
        return JSONResponse(status_code=404, content=api_error("Invoice not found.", "invoice_not_found"))

    return api_success([_line_item_payload(item) for item in invoice.line_items], "Line items fetched successfully.")


@router.post("/invoices/{invoice_id}/items")
def create_line_item(invoice_id: int, db: Session = Depends(get_db), current_customer: Customer = Depends(get_current_customer)):
    """Ruční přidání chybějící položky - LLM extrakce občas rozpoznaný fragment
    textu vůbec nepřevede na položku (viz extraction_warning), tohle je jediný
    způsob, jak takovou položku zákazník sám dodá, aniž by musel celou fakturu
    nahrávat znovu. Vzniká jako prázdný řádek k rovnou vyplnění, ne s vymyšlenými
    daty - stejná zásada jako u LLM (nikdy nevymýšlet konkrétní hodnoty)."""
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.customer_id != current_customer.id:
        return JSONResponse(status_code=404, content=api_error("Invoice not found.", "invoice_not_found"))

    item = LineItem(
        invoice_id=invoice.id,
        description="Nová položka",
        category="uncategorized",
        amount=0.0,
        confidence_score=1.0,
        is_corrected=True,
    )
    db.add(item)

    if invoice.status == InvoiceStatus.NEEDS_REVIEW.value:
        invoice.status = InvoiceStatus.REVIEWED.value

    db.commit()
    db.refresh(item)
    return api_success(_line_item_payload(item), "Line item created successfully.")


@router.patch("/items/{item_id}")
def update_line_item(item_id: int, payload: LineItemUpdate, db: Session = Depends(get_db), current_customer: Customer = Depends(get_current_customer)):
    item = db.get(LineItem, item_id)
    if item is None or item.invoice.customer_id != current_customer.id:
        return JSONResponse(status_code=404, content=api_error("Line item not found.", "line_item_not_found"))

    changes = payload.model_dump(exclude_unset=True)

    if "amount" in changes and "amount_without_vat" not in changes:
        # Ruční oprava celkové částky bez odpovídající opravy základu daně -
        # starý rozpad DPH (dopočítaný z PŮVODNÍ částky) by po změně `amount`
        # zůstal viset a dával by nesmyslné číslo (např. "DPH 21 %" u částky,
        # která tomu vůbec neodpovídá - viz report od zákazníka). Bez jistoty,
        # jaký je nový základ/sazba, je čestnější rozpad smazat a ukázat
        # jen prostý mezisoučet (stejné pravidlo jako u LLM extrakce - nikdy
        # nedopočítávat/neodhadovat DPH, když si nejsme jistí).
        changes["amount_without_vat"] = None
        changes["vat_rate"] = None

    for field, value in changes.items():
        setattr(item, field, value)
    if changes:
        item.is_corrected = True

    invoice = item.invoice
    if "amount" in changes:
        # invoice.total_amount je vlastní sloupec, ne odvozená hodnota - bez tohohle by
        # ruční oprava částky položky zůstala neviditelná v hlavičce i patičce tabulky.
        invoice.total_amount = round(sum(existing.amount for existing in invoice.line_items), 2)

    db.commit()
    db.refresh(item)

    if invoice.status == InvoiceStatus.NEEDS_REVIEW.value:
        invoice.status = InvoiceStatus.REVIEWED.value
        db.commit()

    return api_success(_line_item_payload(item), "Line item updated successfully.")


@router.delete("/items/{item_id}")
def delete_line_item(item_id: int, db: Session = Depends(get_db), current_customer: Customer = Depends(get_current_customer)):
    """Odstranění chybně rozpoznané/duplicitní položky - LLM občas rozdělí
    jeden řádek dokladu na dva, nebo si zachytí fragment, který položkou vůbec
    není (viz extraction_warning)."""
    item = db.get(LineItem, item_id)
    if item is None or item.invoice.customer_id != current_customer.id:
        return JSONResponse(status_code=404, content=api_error("Line item not found.", "line_item_not_found"))

    invoice = item.invoice
    db.delete(item)
    db.flush()

    # invoice.total_amount je vlastní sloupec, ne odvozená hodnota - stejný
    # přepočet jako po ruční opravě částky (viz update_line_item výše).
    invoice.total_amount = round(sum(existing.amount for existing in invoice.line_items), 2)
    if invoice.status == InvoiceStatus.NEEDS_REVIEW.value:
        invoice.status = InvoiceStatus.REVIEWED.value

    db.commit()
    return api_success(None, "Line item deleted successfully.")


@router.post("/invoices/merge")
def merge_invoices(payload: MergeRequest, db: Session = Depends(get_db), current_customer: Customer = Depends(get_current_customer)):
    """Sloučí položky z několika faktur do jedné NOVÉ faktury - zdrojové faktury zůstávají
    beze změny (nemažou se ani se z nich neodebírají položky), tohle je čistě přídavná operace.
    """
    requested_ids = set(payload.invoice_ids)
    invoices = (
        db.query(Invoice)
        .filter(Invoice.id.in_(requested_ids), Invoice.customer_id == current_customer.id)
        .all()
    )
    if len(invoices) != len(requested_ids):
        return JSONResponse(status_code=404, content=api_error("Some invoices were not found.", "invoices_not_found"))

    currencies = {invoice.currency for invoice in invoices}
    if len(currencies) > 1:
        return JSONResponse(
            status_code=400,
            content=api_error("Cannot merge invoices with different currencies.", "currency_mismatch"),
        )

    supplier_names = sorted({invoice.supplier_name for invoice in invoices if invoice.supplier_name})
    invoice_dates = {invoice.invoice_date for invoice in invoices if invoice.invoice_date}
    ocr_texts = [invoice.raw_ocr_text for invoice in invoices if invoice.raw_ocr_text]
    warnings = [invoice.extraction_warning for invoice in invoices if invoice.extraction_warning]
    merged_filename = "Sloučeno: " + ", ".join(invoice.original_filename for invoice in invoices)

    # Když se sloučí faktury od různých dodavatelů, hlavičkové pole nemůže nést jednu
    # pravdivou hodnotu - spojíme jména do jednoho čitelného přehledu, ale skutečný zdroj
    # každé položky zůstává na LineItem.supplier_name/invoice_date (viz níž).
    merged_supplier_name: Optional[str]
    if len(supplier_names) == 1:
        merged_supplier_name = supplier_names[0]
    elif supplier_names:
        merged_supplier_name = ", ".join(supplier_names)
    else:
        merged_supplier_name = None

    merged = Invoice(
        customer_id=current_customer.id,
        original_filename=merged_filename[:255],
        file_path=f"merged:{','.join(str(invoice.id) for invoice in invoices)}",
        status=InvoiceStatus.NEEDS_REVIEW.value,
        supplier_name=merged_supplier_name,
        invoice_date=next(iter(invoice_dates)) if len(invoice_dates) == 1 else None,
        currency=next(iter(currencies)),
        # Nejnižší jistota ze zdrojových faktur - jedna nejistá měna mezi
        # sloučenými doklady má zůstat vidět i po sloučení, ne se "spláchnout".
        currency_confidence=min(invoice.currency_confidence for invoice in invoices),
        raw_ocr_text="\n\n---\n\n".join(ocr_texts) if ocr_texts else None,
        extraction_warning="\n".join(warnings) if warnings else None,
    )
    db.add(merged)
    db.flush()

    total_amount = 0.0
    for invoice in invoices:
        for item in invoice.line_items:
            db.add(LineItem(
                invoice_id=merged.id,
                description=item.description,
                category=item.category,
                amount=item.amount,
                confidence_score=item.confidence_score,
                is_corrected=item.is_corrected,
                supplier_name=item.supplier_name or invoice.supplier_name,
                invoice_date=item.invoice_date or invoice.invoice_date,
                amount_without_vat=item.amount_without_vat,
                vat_rate=item.vat_rate,
            ))
            total_amount += item.amount

    merged.total_amount = round(total_amount, 2)
    db.commit()
    db.refresh(merged)

    result = _invoice_summary_payload(merged)
    result["raw_ocr_text"] = merged.raw_ocr_text or ""
    return api_success(result, "Invoices merged successfully.")


@router.post("/invoices/export")
def export_invoices(payload: ExportRequest, db: Session = Depends(get_db), current_customer: Customer = Depends(get_current_customer)):
    invoices = (
        db.query(Invoice)
        .filter(Invoice.id.in_(payload.invoice_ids), Invoice.customer_id == current_customer.id)
        .all()
    )
    if not invoices:
        return JSONResponse(status_code=404, content=api_error("No matching invoices found for this customer.", "invoices_not_found"))

    output_path = export_invoices_to_excel(invoices, current_customer.excel_template_config)

    for invoice in invoices:
        invoice.status = InvoiceStatus.EXPORTED.value
    db.commit()

    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="invoices_export.xlsx",
    )
