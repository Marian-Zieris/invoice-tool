"""Test fixtures. Testy záměrně neběží proti OCR/LLM pipeline (žádný reálný
Tesseract/RapidOCR/Groq požadavek) - pokrývají auth, autorizaci a validaci
uploadu, tedy přesně ty vrstvy, které tenhle audit opravoval a kde by tichá
regrese příště nejvíc bolela. Faktury pro testy autorizace se zakládají přímo
v DB, ne přes skutečný upload+zpracování.
"""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key-not-for-production")
os.environ.setdefault("GROQ_KEY", "test-groq-key-unused-in-tests")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_invoice_tool.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app
from app.rate_limit import _attempts

TEST_DB_PATH = "./test_invoice_tool.db"
engine = create_engine(f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _no_real_ocr_llm(monkeypatch):
    """FastAPI/Starlette's TestClient runs BackgroundTasks synchronously as
    part of the request - bez tohohle patche by "upload validního souboru"
    test skutečně zavolal Tesseract/RapidOCR a Groq API. Testy tady cíleně
    pokrývají validaci/autorizaci kolem uploadu, ne přesnost OCR/LLM extrakce."""
    monkeypatch.setattr("app.routers.upload.process_invoice", lambda invoice_id: None)


@pytest.fixture
def client():
    """Čisté schéma pro každý test - jde o testovací SQLite soubor, ne o
    produkční appku, takže create_all/drop_all je tady v pořádku (na rozdíl
    od skutečného provozu appky, kde je jediný způsob správy schématu Alembic).
    Tabulky se vytvoří PŘED spuštěním TestClient (a tedy před startup hookem
    appky, který spouští watchdog smyčku dotazující se do DB) - jinak by první
    dotaz mohl narazit na ještě neexistující tabulky.
    """
    Base.metadata.create_all(bind=engine)
    _attempts.clear()  # rate limiter drží stav v paměti procesu mezi testy
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def admin_headers():
    return {"X-Admin-Key": os.environ["ADMIN_API_KEY"]}


@pytest.fixture
def db_session():
    """Přímý DB přístup pro test setup (např. založit fakturu bez skutečného
    OCR/LLM zpracování) - používat jen pro arrange fázi testu, ne pro assert."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
