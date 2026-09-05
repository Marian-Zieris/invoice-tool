# Invoice OCR Tool — Kompletní specifikace MVP

Tento dokument popisuje, jak má vypadat **hotová, funkční verze MVP**. Je určený jako vstup pro AI coding agenta (Claude Code, Copilot agent, apod.) — obsahuje vše potřebné k tomu, aby agent mohl aplikaci postavit od začátku do konce bez dalších doplňujících otázek k základní vizi.

---

## 1. Co aplikace dělá (produktový popis)

Webová aplikace pro řemeslníky a mikrofirmy. Zákazník se přihlásí, nahraje složku s fakturami/účtenkami (PDF, foto, scan), aplikace:

1. Předzpracuje obrázek (narovnání, kontrast).
2. OCR vytáhne surový text.
3. LLM (Groq API, model `openai/gpt-oss-120b`) z textu vytáhne strukturovaná data: dodavatel, datum, položky, kategorie, částky — podle pravidel kategorizace nastavených pro daného zákazníka.
4. Zákazník v přehledné tabulce zkontroluje/opraví data — nízko-jistotové hodnoty jsou zvýrazněné.
5. Po potvrzení se vyexportuje Excel ve formátu, na jaký je zákazník zvyklý.

**Pozn.:** Původní selling point "žádná data neputují k externí AI" už neplatí — kvůli rychlosti a stabilitě se extrakce přepnula z lokální Ollamy na Groq cloud API. OCR text tedy nově opouští server poskytovatele a jde k třetí straně (Groq).

## 2. Rozsah MVP — co MUSÍ fungovat

- Registrace/přihlášení zákazníka (jednoduché, email + heslo).
- Upload více souborů najednou (PDF i obrázky).
- Automatické zpracování na pozadí (uživatel nečeká s visící stránkou).
- Review obrazovka: seznam faktur, stavy zpracování, tabulka položek se zvýrazněním nejistých hodnot, možnost inline opravy.
- Export vybraných/všech faktur do Excelu podle šablony zákazníka.
- Konfigurace per zákazník: vlastní kategorie, vlastní formát výstupního Excelu (nastavuje admin/vy při onboardingu, ne sám zákazník v MVP).

## Co NENÍ součástí MVP (vědomě odloženo)

- Samoobslužná registrace bez zásahu admina (zatím zákazníky zakládáte ručně).
- Platební brána / fakturace v appce (řeší se mimo appku).
- Mobilní aplikace (jen responzivní web).
- Víc jazyků UI (jen čeština).
- Automatické učení se z oprav uživatele (zatím žádný feedback loop do promptu/modelu).

## 3. Uživatelské role

- **Customer** — řemeslník/mikrofirma, nahrává faktury, kontroluje data, exportuje.
- **Admin (vy)** — zakládá zákazníky, nastavuje jejich kategorie a Excel šablonu, nemá zatím žádné UI, řeší se přímým zásahem do DB nebo jednoduchým interním endpointem.

## 4. Tech stack (finální rozhodnutí, neměnit bez důvodu)

| Vrstva | Technologie | Poznámka |
|---|---|---|
| Backend | FastAPI (Python 3.11) | |
| ORM / migrace | SQLAlchemy 2.0 + Alembic | **Nikdy nepoužívat `Base.metadata.create_all` v běžícím projektu** — jen Alembic migrace |
| DB | PostgreSQL | |
| Frontend | React + TypeScript + Vite + Tailwind v4 (`frontend/`) | Samostatný Docker kontejner (nginx), volá backend přes `/api/*` reverse proxy — API kontejner o frontendu neví |
| Preprocessing obrázků | OpenCV (`opencv-python-headless`) | |
| OCR | Tesseract (`pytesseract`) | Vyžaduje binárku `tesseract-ocr` + `tesseract-ocr-ces` nainstalovanou v Dockerfile — **ověřit funkčnost přes `tesseract --version` a `tesseract --list-langs` v kontejneru, ne jen předpokládat** |
| PDF → obrázek | `pdf2image` (potřebuje `poppler-utils` v Dockerfile) | |
| LLM extrakce | Groq API (`openai` SDK, `base_url=https://api.groq.com/openai/v1`), model `openai/gpt-oss-120b` | Klíč v `.env` jako `GROQ_KEY`, žádná lokální služba |
| Export | `pandas` + `openpyxl` | |
| Balíčky | `uv` + `pyproject.toml` | |
| Kontejnerizace | Docker Compose | produkční `docker-compose.yml` (bez reloadu/mountu) + `docker-compose.override.yml` (dev extras) |
| Hosting | VPS (Hetzner CPX21/31 nebo obdoba), ne PaaS (Heroku) kvůli výkonu pro Ollamu | |
| Reverse proxy / HTTPS | nginx + certbot (Let's Encrypt) | |

## 5. Datový model

```python
class Customer:
    id: int
    email: str (unique)
    password_hash: str
    excel_template_config: JSON   # mapování sloupců/formátu výstupního Excelu
    category_rules: JSON          # seznam kategorií a pravidel pro LLM prompt
    created_at: datetime

class Invoice:
    id: int
    customer_id: FK -> Customer
    original_filename: str
    file_path: str
    status: str   # uploaded | processing | needs_review | reviewed | exported | ocr_failed | extraction_failed
    raw_ocr_text: text, nullable
    supplier_name: str, nullable
    invoice_date: date, nullable
    total_amount: float, nullable
    currency: str, default "CZK"
    created_at: datetime

class LineItem:
    id: int
    invoice_id: FK -> Invoice
    description: str
    category: str
    amount: float
    confidence_score: float   # 0.0–1.0, řídí zvýraznění v review UI
    is_corrected: bool, default False
```

Stavový diagram `Invoice.status`:

```
uploaded → processing → needs_review → reviewed → exported
                ↓
          ocr_failed / extraction_failed  (chyba se ukáže uživateli, ne tichý pád)
```

## 6. API endpointy

| Metoda | Cesta | Popis |
|---|---|---|
| POST | `/auth/register` | admin-only (vyžaduje hlavičku `X-Admin-Key`) |
| POST | `/auth/login` | vrací session/JWT |
| POST | `/customers` | admin-only (vyžaduje hlavičku `X-Admin-Key`), vytvoří zákazníka + jeho config |
| POST | `/invoices/upload` | multi-file upload, spustí zpracování na pozadí |
| GET | `/invoices` | seznam faktur přihlášeného zákazníka se statusy |
| GET | `/invoices/{id}` | detail faktury vč. `raw_ocr_text` a stavu |
| GET | `/invoices/{id}/items` | položky faktury pro review tabulku |
| PATCH | `/items/{id}` | ruční oprava položky, nastaví `is_corrected=true` |
| POST | `/invoices/export` | vezme seznam ID faktur, vrátí Excel ke stažení |
| GET | `/health` | healthcheck |

## 7. Zpracovatelská pipeline (background task)

1. **Upload** → soubor se uloží, `Invoice` se založí se statusem `uploaded`, request se hned vrátí.
2. **Background job**:
   - Pokud je vstup PDF → převést na obrázek(y) přes `pdf2image`.
   - `preprocess.py` → OpenCV vyčistí obrázek.
   - `ocr.py` → Tesseract vytáhne text → uloží do `raw_ocr_text`. **Pokud je výstup prázdný, status jde na `ocr_failed`, NE na `needs_review` s prázdnými daty.**
   - `extract.py` → text jde do Ollamy s promptem obsahujícím `customer.category_rules` → očekává se strukturovaný JSON (supplier_name, invoice_date, total_amount, currency, line_items[]).
   - Validace výstupu LLM: pokud model vrátí nevalidní JSON nebo prázdná data, status jde na `extraction_failed`, ne fallback na vymyšlené "Neznámý dodavatel" hodnoty.
   - Úspěch → uloží se `LineItem` záznamy, status `needs_review`.
3. **Žádný krok nesmí tiše selhat a předstírat úspěch** — chybové stavy musí být viditelné v `Invoice.status` a v UI.

## 8. LLM extrakce — princip promptu

- Systémový prompt obsahuje: seznam povolených kategorií z `customer.category_rules`, formát požadovaného výstupu (přesný JSON schema), instrukci "pokud si nejsi jistý hodnotou, sniž confidence_score, nevymýšlej si číslo."
- Model musí vracet `confidence_score` pro každou položku — to pohání zvýraznění v review UI (práh např. < 0.6 = zvýraznit).
- Výstup se parsuje a validuje (např. přes Pydantic model) — při chybě parsování jde faktura do `extraction_failed`, ne do potichu prázdného výsledku.

## 9. Review UI (React SPA, `frontend/`)

- Jedna obrazovka `/` (po přihlášení) — vlevo seznam faktur se stavy (barevně odlišené: needs_review žlutě/warn, ocr_failed/extraction_failed červeně, reviewed/exported zeleně), vpravo detail vybrané faktury.
- Detail: tabulka položek, řádky s `confidence_score` < 0.6 mají zvýrazněné pozadí a varovnou ikonu, inline editace (popis/kategorie/částka) přes `PATCH /items/{id}` bez reloadu — klik na buňku, uložení při rozostření/Enter.
- Tlačítko "Exportovat" — buď jedna faktura, nebo hromadně přes checkboxy v seznamu.
- Vizuální styl: "liquid glass" (matné panely, jemné barevné gradienty na pozadí), přepínač světlý/tmavý režim (výchozí tmavý), akcentní barva měď/bronz.
- Běží jako čistě statická produkční build (Vite → nginx) ve vlastním kontejneru; veškerá komunikace s API jde přes `/api/*`, které nginx přeposílá na `web:8000` a strhává prefix — frontend kontejner je jediné místo, které zná existenci obou služeb, backend o něm neví vůbec.

## 10. Export

- `POST /invoices/export` vezme seznam ID, pro každou fakturu vezme `LineItem` záznamy, sestaví DataFrame, namapuje sloupce podle `customer.excel_template_config` (např. pořadí sloupců, názvy hlaviček přesně jak je zákazník zvyklý), vrátí `.xlsx` soubor ke stažení.

## 11. Bezpečnost a provoz

- Žádné hardcoded credentials — vše přes `.env` (mimo git, viz `.gitignore`/`.dockerignore`).
- Admin-only endpointy (`POST /auth/register`, `POST /customers`, `POST /customers/{id}/template`) chráněné sdíleným klíčem v hlavičce `X-Admin-Key` (`ADMIN_API_KEY` v `.env`) — bez něj vrací `401`.
- Hesla hashovaná (bcrypt/argon2), nikdy plaintext.
- HTTPS všude v produkci (certbot).
- Non-root uživatel v Dockeru.
- DB port neexponovaný navenek v produkční compose konfiguraci.
- Uploadnuté soubory a `raw_ocr_text` obsahují citlivá finanční data — žádné zbytečně dlouhé uchovávání, zvážit periodické mazání starých souborů z disku po úspěšném exportu.

## 12. Definice hotovo (acceptance criteria)

MVP je hotové, když:

1. Zákazník se může přihlásit a nahrát PDF i fotku faktury.
2. OCR reálně vrací neprázdný text u ≥ 90 % testovací sady (viz `eval.py` / `eval_data/`) — **ne fallback data**.
3. LLM extrakce vrátí validní strukturovaná data se smysluplným `confidence_score` u stejné testovací sady.
4. Review UI zobrazí data a zvýrazní nejisté hodnoty; oprava položky se reálně uloží do DB.
5. Export vytvoří `.xlsx` soubor odpovídající šabloně zákazníka a soubor se dá bez chyby otevřít v Excelu.
6. Celý stack (web + db + frontend) naběhne přes `docker compose up` bez ručních zásahů (migrace se spustí automaticky).
7. Žádné tajemství (hesla, DB credentials) nejsou commitnuté v gitu.

## 13. Známé chyby z předchozích iterací — nedělat znovu

- **Nepoužívat `Base.metadata.create_all`** jako jediný způsob správy schématu — vždy Alembic.
- **Neschovávat selhání OCR/LLM za fallback/mock data** ("Neznámý dodavatel", "Nezjištěna položka") — chyba musí být viditelná ve stavu faktury.
- **Ověřit, že Tesseract binárka je v image reálně nainstalovaná** (`tesseract --version` v kontejneru) — nespoléhat na to, že apt-get řádek v Dockerfile "asi funguje".
- **Nehardcodovat DB credentials** do `docker-compose.yml`.
- **Nemountovat kód a nepoužívat `--reload` v produkční konfiguraci.**

## 14. Business kontext (pro pochopení proč, ne jak stavět kód)

- Cílovka: čeští řemeslníci a mikrofirmy.
- Cena: 5 000–8 000 Kč jednorázově (+/- 2 000 Kč podle náročnosti dat), zatím bez měsíčního paušálu.
- Autor produktu je 17letý samouk-programátor, projekt je zatím v testovací fázi s očekáváním 0–2 zákazníků z první vlny cold-emailu.