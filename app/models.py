import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class InvoiceStatus(str, enum.Enum):
    """Stavy Invoice.status - sloupec zůstává obyčejný String (žádná DB enum
    constraint), tohle je jen jednotný zdroj pravdy pro Python kód."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    REVIEWED = "reviewed"
    EXPORTED = "exported"
    OCR_FAILED = "ocr_failed"
    EXTRACTION_FAILED = "extraction_failed"


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    excel_template_config: Mapped[dict] = mapped_column(JSON, default=dict)
    category_rules: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    invoices: Mapped[list["Invoice"]] = relationship(back_populates="customer", cascade="all, delete-orphan")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    original_filename: Mapped[str] = mapped_column(String)
    file_path: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default=InvoiceStatus.UPLOADED.value)
    raw_ocr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supplier_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    invoice_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    total_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String, default="CZK")
    # Krátká poznámka od LLM - vyplní se jen když model narazil na fragment textu, který
    # vypadal jako další položka, ale nešel spolehlivě přiřadit (viz llm.py) - signál pro
    # zákazníka, že faktura může mít víc položek, než kolik se jich reálně vytěžilo.
    extraction_warning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped["Customer"] = relationship(back_populates="invoices")
    line_items: Mapped[list["LineItem"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    description: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String, default="uncategorized")
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    # Denormalizováno z Invoice v okamžiku vzniku položky - když se pak víc faktur sloučí
    # do jedné (viz POST /invoices/merge), hlavička sloučené faktury může mít víc různých
    # dodavatelů/dat najednou, ale každá jednotlivá položka si tu svůj skutečný původ nese dál.
    supplier_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    invoice_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # Vyplní se JEN pokud doklad sám uvádí rozpis DPH (typicky faktura od plátce DPH) -
    # `amount` zůstává částka VČETNĚ DPH jako dosud. Nikdy se nedopočítává/neodhaduje -
    # spousta živnostníků/mikrofirem (cílovka appky) DPH neplatí a doklad ho vůbec nemá.
    amount_without_vat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vat_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="line_items")