import os
import uuid
from typing import Any, Dict, List, Optional

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.models import Invoice

EXPORT_DIR = os.environ.get("EXPORT_DIR") or os.path.join(os.getcwd(), "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

# Interní klíč -> výchozí hlavička sloupce, pokud zákazník nemá vlastní excel_template_config.
DEFAULT_COLUMNS: Dict[str, str] = {
    "invoice_id": "ID faktury",
    "original_filename": "Soubor",
    "supplier_name": "Dodavatel",
    "invoice_date": "Datum",
    "description": "Popis položky",
    "category": "Kategorie",
    "amount": "Částka",
    "currency": "Měna",
    "confidence_score": "Jistota",
    "is_corrected": "Opraveno ručně",
    "amount_without_vat": "Základ daně",
    "vat_rate": "Sazba DPH (%)",
}

# Sloupce reálného (bez šablony) exportu - jen účetně relevantní údaje, žádné interní
# QA metadata (ID, jistota OCR, "opraveno ručně") - to nikam do faktury pro zákazníka nepatří.
_HEADERS = ["Datum", "Dodavatel", "Popis položky", "Kategorie", "Částka", "Měna"]
_COLUMN_WIDTHS = [12, 26, 42, 16, 13, 8]

_HEADER_FILL = PatternFill(start_color="1F2A24", end_color="1F2A24", fill_type="solid")
_HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
_GROUP_FILL = PatternFill(start_color="F0EDE7", end_color="F0EDE7", fill_type="solid")
_GROUP_FONT = Font(bold=True, size=10.5, color="3A3226")
_SUBTOTAL_FONT = Font(bold=True, italic=True, size=10, color="5B5346")
_GRAND_TOTAL_FONT = Font(bold=True, size=11.5)
_THIN_BOTTOM = Border(bottom=Side(style="thin", color="D8D2C4"))
_AMOUNT_FORMAT = "#,##0.00"
_RIGHT = Alignment(horizontal="right", vertical="center")
_LEFT = Alignment(horizontal="left", vertical="center")


def _row_for_line_item(invoice: Invoice, item) -> Dict[str, Any]:
    item_date = item.invoice_date or invoice.invoice_date
    return {
        "invoice_id": invoice.id,
        "original_filename": invoice.original_filename,
        "supplier_name": item.supplier_name or invoice.supplier_name or "",
        "invoice_date": item_date.isoformat() if item_date else "",
        "description": item.description,
        "category": item.category,
        "amount": item.amount,
        "currency": invoice.currency,
        "confidence_score": item.confidence_score,
        "is_corrected": item.is_corrected,
        "amount_without_vat": item.amount_without_vat if item.amount_without_vat is not None else "",
        "vat_rate": item.vat_rate if item.vat_rate is not None else "",
    }


def _build_dataframe(invoices: List[Invoice], columns: List[str]) -> pd.DataFrame:
    rows = []
    for invoice in invoices:
        for item in invoice.line_items:
            row = _row_for_line_item(invoice, item)
            rows.append({key: row.get(key, "") for key in columns})
    return pd.DataFrame(rows, columns=columns)


def _fill_row(sheet, row: int, fill: PatternFill, span: int) -> None:
    for col_idx in range(1, span + 1):
        sheet.cell(row=row, column=col_idx).fill = fill


def _vat_breakdown(items: List[Any]) -> Optional[tuple]:
    """Vrátí (základ daně, [(popis sazby, částka DPH), ...]) - ale JEN pokud má úplně
    každá položka faktury vyplněné amount_without_vat. Zdroj (viz llm.py) tam dává hodnotu
    výhradně když ji doklad sám uvádí, takže "chybí u některé položky" typicky znamená
    "doklad DPH vůbec neřeší" (např. dodavatel není plátce) - v tom případě nikdy
    nedopočítáváme přibližný/domnělý rozpad, radši ukážeme jen prostý mezisoučet.
    """
    if not items or any(item.amount_without_vat is None for item in items):
        return None

    vat_base_total = round(sum(item.amount_without_vat for item in items), 2)
    rate_totals: Dict[Optional[float], float] = {}
    for item in items:
        rate_totals[item.vat_rate] = rate_totals.get(item.vat_rate, 0.0) + (item.amount - item.amount_without_vat)

    rate_rows = [
        (f"DPH {rate:g} %" if rate is not None else "DPH", round(rate_totals[rate], 2))
        for rate in sorted(rate_totals, key=lambda r: (r is None, r))
    ]
    return vat_base_total, rate_rows


def _write_label_row(sheet, row: int, span: int, label: str, amount: float, currency: str, font: Font) -> None:
    sheet.cell(row=row, column=span - 2, value=label).font = font
    sheet.cell(row=row, column=span - 2).alignment = _RIGHT
    amount_cell = sheet.cell(row=row, column=span - 1, value=amount)
    amount_cell.font = font
    amount_cell.number_format = _AMOUNT_FORMAT
    amount_cell.alignment = _RIGHT
    sheet.cell(row=row, column=span, value=currency).font = font


def _build_default_workbook(invoices: List[Invoice]) -> Workbook:
    """Sestaví čitelný report bez šablony: hlavička, faktury seskupené s mezisoučtem,
    celkový součet (rozpadlý po měnách, pokud se v exportu mísí víc měn najednou)."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Export"

    span = len(_HEADERS)
    for col_idx, (header, width) in enumerate(zip(_HEADERS, _COLUMN_WIDTHS), start=1):
        cell = sheet.cell(row=1, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _RIGHT if col_idx >= 5 else _LEFT
        sheet.column_dimensions[get_column_letter(col_idx)].width = width
    sheet.row_dimensions[1].height = 20
    sheet.freeze_panes = "A2"

    row = 2
    currency_totals: Dict[str, float] = {}

    for invoice in invoices:
        supplier = invoice.supplier_name or "Nerozpoznáno"

        group_cell = sheet.cell(row=row, column=1, value=invoice.original_filename)
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
        group_cell.font = _GROUP_FONT
        group_cell.alignment = _LEFT
        _fill_row(sheet, row, _GROUP_FILL, span)
        sheet.row_dimensions[row].height = 19
        row += 1

        subtotal = 0.0
        for item in invoice.line_items:
            item_date = item.invoice_date or invoice.invoice_date
            item_supplier = item.supplier_name or supplier
            sheet.cell(row=row, column=1, value=item_date.strftime("%d.%m.%Y") if item_date else "")
            sheet.cell(row=row, column=2, value=item_supplier)
            sheet.cell(row=row, column=3, value=item.description)
            sheet.cell(row=row, column=4, value=item.category)
            amount_cell = sheet.cell(row=row, column=5, value=item.amount)
            amount_cell.number_format = _AMOUNT_FORMAT
            amount_cell.alignment = _RIGHT
            sheet.cell(row=row, column=6, value=invoice.currency).alignment = _RIGHT
            subtotal += item.amount
            row += 1

        vat_info = _vat_breakdown(invoice.line_items)
        if vat_info is not None:
            vat_base_total, rate_rows = vat_info
            _write_label_row(sheet, row, span, "Základ daně", vat_base_total, invoice.currency, _SUBTOTAL_FONT)
            row += 1
            for label, vat_amount in rate_rows:
                _write_label_row(sheet, row, span, label, vat_amount, invoice.currency, _SUBTOTAL_FONT)
                row += 1
            _write_label_row(sheet, row, span, "Celkem s DPH", subtotal, invoice.currency, _SUBTOTAL_FONT)
        else:
            _write_label_row(sheet, row, span, "Mezisoučet", subtotal, invoice.currency, _SUBTOTAL_FONT)

        for col_idx in range(1, span + 1):
            sheet.cell(row=row, column=col_idx).border = _THIN_BOTTOM
        row += 2  # mezera mezi fakturami

        currency_totals[invoice.currency] = currency_totals.get(invoice.currency, 0.0) + subtotal

    for currency, total in currency_totals.items():
        label = "Celkem" if len(currency_totals) == 1 else f"Celkem ({currency})"
        _write_label_row(sheet, row, span, label, total, currency, _GRAND_TOTAL_FONT)
        row += 1

    return workbook


def export_invoices_to_excel(invoices: List[Invoice], excel_template_config: Optional[Dict[str, Any]] = None) -> str:
    """Vyexportuje LineItem záznamy vybraných faktur do .xlsx podle šablony zákazníka."""
    config = excel_template_config if isinstance(excel_template_config, dict) else {}

    output_name = f"export_{uuid.uuid4()}.xlsx"
    output_path = os.path.join(EXPORT_DIR, output_name)

    template_path = config.get("template_path")
    if template_path and os.path.exists(template_path):
        columns: List[str] = config.get("columns") or list(DEFAULT_COLUMNS.keys())
        headers: List[str] = config.get("headers") or [DEFAULT_COLUMNS.get(col, col) for col in columns]
        dataframe = _build_dataframe(invoices, columns)

        workbook = load_workbook(template_path)
        sheet_name = config.get("sheet_name") or workbook.sheetnames[0]
        sheet = workbook[sheet_name] if sheet_name in workbook.sheetnames else workbook.active
        start_row = int(config.get("start_row", 2))

        for col_idx, header in enumerate(headers, start=1):
            sheet.cell(row=start_row - 1, column=col_idx, value=header)

        for row_offset, row in enumerate(dataframe.itertuples(index=False)):
            for col_idx, value in enumerate(row, start=1):
                sheet.cell(row=start_row + row_offset, column=col_idx, value=value)

        workbook.save(output_path)
    else:
        workbook = _build_default_workbook(invoices)
        workbook.save(output_path)

    return output_path
