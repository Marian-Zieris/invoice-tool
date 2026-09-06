import json
import logging
import os
from typing import Any, Dict, List, Optional

from openai import APIError, APITimeoutError, OpenAI
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_KEY environment variable is required to call the Groq API.")

GROQ_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_TIMEOUT_SECONDS = float(os.environ.get("GROQ_TIMEOUT_SECONDS", "60"))

MAX_INPUT_CHARS = 12000

_client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL, timeout=GROQ_TIMEOUT_SECONDS)


class ExtractionError(Exception):
    """LLM vrátil nevalidní/neúplný výstup - faktura musí jít do extraction_failed, ne fallback dat."""


class LineItemExtraction(BaseModel):
    description: str = Field(min_length=1)
    category: str = "uncategorized"
    amount: float
    confidence_score: float = Field(ge=0.0, le=1.0)
    amount_without_vat: Optional[float] = None
    vat_rate: Optional[float] = None


class InvoiceExtraction(BaseModel):
    supplier_name: Optional[str] = None
    invoice_date: Optional[str] = None
    currency: Optional[str] = "CZK"
    # 0.0-1.0: jak jistý si model je měnou samotnou, ne částkami. Nízká hodnota
    # typicky znamená "text neobsahoval žádnou stopu po měně, CZK je jen
    # výchozí odhad" - bez tohohle pole zůstávala špatně určená měna neviditelná
    # v review UI, protože confidence_score u položek se váže na popis/částku,
    # ne na měnu (viz audit, nález D2 - IDR účtenka omylem jako "91 000 CZK").
    currency_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    total_amount: Optional[float] = None
    line_items: List[LineItemExtraction] = Field(default_factory=list)
    extraction_warning: Optional[str] = None


def _resolve_categories(category_rules: Any) -> List[str]:
    if isinstance(category_rules, dict):
        categories = category_rules.get("categories")
    elif isinstance(category_rules, list):
        categories = category_rules
    else:
        categories = None
    return categories or ["uncategorized"]


def _build_system_prompt(categories: List[str]) -> str:
    schema_hint = {
        "supplier_name": "string nebo null",
        "invoice_date": "YYYY-MM-DD nebo null",
        "currency": "ISO 4217 kod meny (CZK, EUR, USD, IDR, ...)",
        "currency_confidence": "0.0-1.0 - viz instrukce nize",
        "total_amount": "cislo nebo null",
        "line_items": [
            {
                "description": "string",
                "category": f"jedna z: {', '.join(categories)}",
                "amount": "cislo - CELKOVA cena polozky VCETNE DPH",
                "confidence_score": "0.0-1.0",
                "amount_without_vat": "cislo nebo null - cena bez DPH, jen pokud ji doklad sam uvadi",
                "vat_rate": "cislo nebo null - sazba DPH v procentech (napr. 21, 12, 0), jen pokud je na dokladu",
            }
        ],
        "extraction_warning": "string nebo null - viz instrukce nize",
    }

    return (
        "Jsi asistent pro extrakci strukturovanych dat z ceskych/anglickych faktur a uctenek.\n"
        "Z OCR textu, ktery dostanes jako uzivatelskou zpravu, vytahni data a vrat POUZE validni JSON "
        f"objekt presne v tomto formatu:\n{json.dumps(schema_hint, ensure_ascii=False, indent=2)}\n\n"
        f"Povolene kategorie polozek: {', '.join(categories)}.\n"
        "Pokud si nejsi jisty hodnotou, sniz confidence_score smerem k 0, ale NEVYMYSLI si cislo ani nazev - "
        "pokud hodnotu v textu nenajdes, pouzij null (u supplier_name/invoice_date/total_amount) nebo polozku vynech.\n"
        "Castky pis jako cisla bez mezer a bez symbolu meny.\n"
        "Desetinny oddelovac u CZK/EUR castek: pokud mena vychazi jako CZK nebo EUR, cti JAK CARKU TAK TECKU jako "
        "desetinne misto, ne jako oddelovac tisic - levne tiskarny uctenek casto tisknou tecku misto carky. "
        "Priklad: '25.000' i '25,000 Kc' na ceske/eurove uctence znamena castku 25 (ne 25000). Tecku jako "
        "oddelovac TISIC pouzivej jen u jinych men (napr. IDR, VND, kde castky bezne jsou v tisicich) nebo kdyz "
        "cislo obsahuje vic teckovych/carkovych skupin za sebou (napr. '1.234.567').\n"
        "Menu urcuj aktivne z textu - hledej symboly (Kc, Kč, $, €, Rp, Rs, £) i psane kody (CZK, EUR, USD, IDR). "
        "Teprve kdyz text neobsahuje vubec zadnou stopu po mene, pouzij CZK jako rozumny vychozi odhad "
        "(nikdy nevracej null u currency).\n"
        "currency_confidence: 1.0 kdyz jsi menu nasel jako jasnou stopu v textu (symbol nebo kod). Pokud jsi "
        "CZK pouzil jen jako vychozi odhad bez jakekoliv stopy v textu, nastav currency_confidence NIZKO (pod 0.4) "
        "- tohle pole existuje presne pro tenhle pripad, aby uzivatel videl, ze mena je jen odhad, ne precteny udaj.\n"
        "DPH (amount_without_vat, vat_rate) vyplnuj VYHRADNE kdyz je doklad sam explicitne uvadi (napr. sloupce "
        "'zaklad dane'/'zaklad'/'bez DPH' a 'sazba'/'DPH%', nebo souhrnna tabulka 'Vycisleni DPH'). Spousta "
        "zivnostniku a mikrofirem NENI platci DPH a jejich doklady zadne DPH neobsahuji - v takovem pripade "
        "NIKDY DPH nedopocitavej ani neodhaduj, nech obe pole null.\n"
        "extraction_warning: pokud v OCR textu narazis na fragment, ktery vypada jako dalsi polozka/castka "
        "(napr. cislo bez jasneho popisu, useknuty radek, necitelny shluk znaku uprostred seznamu polozek), ale "
        "je natolik nejasny, ze ho nejde spolehlive prevest na polozku s popisem a castkou, NEVKLADEJ ho do "
        "line_items (jak uz plati vyse) - misto toho strucne (jednou vetou) napis do extraction_warning, ze "
        "doklad pravdepodobne obsahuje dalsi polozky, ktere se nepodarilo precist. Pokud text pusobi kompletne "
        "a citelne, nech extraction_warning null - nepouzivej ho jako obecnou omluvu za nizkou jistotu."
    )


def _call_groq(system_prompt: str, raw_text: str) -> str:
    try:
        completion = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_text[:MAX_INPUT_CHARS]},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
    except APITimeoutError as exc:
        raise ExtractionError(f"Groq API request timed out: {exc}") from exc
    except APIError as exc:
        raise ExtractionError(f"Groq API request failed: {exc}") from exc

    choice = completion.choices[0] if completion.choices else None
    content = choice.message.content if choice and choice.message else None
    return content or ""


def extract_invoice_data(raw_text: str, category_rules: Optional[Any]) -> InvoiceExtraction:
    """Pošle OCR text do Groq API a vrátí validovaná strukturovaná data.

    Nikdy nevrací fallback/mock hodnoty - při jakékoliv chybě zvedá ExtractionError.
    """
    if not raw_text.strip():
        raise ExtractionError("Cannot extract invoice data from empty OCR text.")

    categories = _resolve_categories(category_rules or {})
    system_prompt = _build_system_prompt(categories)
    response_text = _call_groq(system_prompt, raw_text)

    if not response_text.strip():
        raise ExtractionError("Groq returned an empty response.")

    try:
        parsed: Dict[str, Any] = json.loads(response_text)
    except json.JSONDecodeError as exc:
        logger.warning("Groq response was not valid JSON: %s", response_text[:500])
        raise ExtractionError(f"Groq response is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ExtractionError("Groq response JSON is not an object.")

    try:
        extraction = InvoiceExtraction(**parsed)
    except ValidationError as exc:
        logger.warning("Groq response failed schema validation: %s", exc)
        raise ExtractionError(f"Groq response failed schema validation: {exc}") from exc

    if extraction.total_amount is None and not extraction.line_items:
        raise ExtractionError("Groq returned no total_amount and no line_items - nothing usable to save.")

    return extraction
