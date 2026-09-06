# PROGRESS — cesta k prodejnému stavu

Vychází z nezávislého auditu (2026-09-06). Pracuji samostatně bod po bodu,
od nejkritičtějšího. Každá položka: plán → implementace → ověření → commit.

Stavy: `[ ]` čeká, `[~]` rozpracováno, `[x]` hotovo a ověřeno.

## KRITICKÉ (blokuje prodej)

- [x] **K1 — Docker volumes vlastněné rootem (upload/export/šablony padají na 500)**
  Řešení: build-time `chown` na `/app` samo o sobě nestačí pro named volumes
  (Docker při prvním připojení prázdného volume vytvoří mountpoint jako root,
  build-time vlastnictví nepřevezme spolehlivě). Místo toho kontejner teď
  startuje jako root, `entrypoint.sh` při KAŽDÉM startu udělá `mkdir -p` +
  `chown -R appuser:appuser` na `uploads/exports/excel_templates` (idempotentní,
  opraví i už existující špatně vlastněné volumes) a pak přes `setpriv
  --reuid=appuser --regid=appuser --init-groups` natrvalo přepne na appuser
  pro `alembic upgrade head` i samotný uvicorn proces. `USER appuser` v
  Dockerfile odstraněn (dřív bránil entrypointu dělat cokoliv jako root).
  Ověřeno: `docker compose down` + smazání volumes + `up --build` od nuly →
  `docker exec ... ls -la` ukazuje `appuser:appuser` na všech třech adresářích,
  `docker top` potvrzuje, že uvicorn i migrace běží pod uid 1000, ne 0. Plné
  E2E: upload skutečné účtenky → `needs_review` s daty → export → validní
  `.xlsx` (potvrzeno `file` utilitou). Soubory: `Dockerfile`, `entrypoint.sh`.

- [x] **K2 — Bez rate limitu na `/auth/login` (brute force)**
  Řešení: `app/rate_limit.py` - in-memory limiter (5 pokusů/5 min na kombinaci
  IP+email, 20/5 min na IP napříč emaily proti credential stuffingu), `/auth/login`
  vrací `429` + `Retry-After` po překročení. Úspěšný login počítadlo pro danou
  kombinaci smaže, neúspěšný ho navyšuje. Bonus nález při implementaci: backend
  port `8000` byl v produkční `docker-compose.yml` publikovaný přímo ven, což by
  šlo použít k obejití nginx a PODVRŽENÍ `X-Forwarded-For` (limiter by pak počítal
  útočníkovi jinou IP, než jakou skutečně má) - port přesunut do
  `docker-compose.override.yaml` (jen pro lokální dev), produkce ho už nepublikuje.
  Ověřeno živě: 5× špatné heslo → `401`, 6.-8. pokus → `429 rate_limited`.
  Soubory: `app/rate_limit.py` (nový), `app/routers/auth.py`, `docker-compose.yml`,
  `docker-compose.override.yaml`.

- [x] **K3 — Žádné zálohování dat**
  Řešení: nová `backup` služba v `docker-compose.yml` (image `postgres:15-alpine`,
  žádná nová závislost) běží ve smyčce a jednou denně spustí `scripts/backup_db.sh`
  (`pg_dump | gzip` do named volume `db_backups`, rotace záloh starších než
  `BACKUP_KEEP_DAYS`, default 14 dní). Přidán i `scripts/restore_db.sh` pro
  obnovu. Běží automaticky jako součást `docker compose up` bez ručního cronu
  na hostiteli - odpovídá SPEC §12.6 duchu "žádné ruční zásahy".
  Ověřeno živě: spuštění `backup` služby vytvořilo `invoices_20260906_104333.sql.gz`,
  reálně jsem ho obnovil do dočasné DB (`restore_test`) a ověřil, že zákaznický
  účet (`zieris.marian@gmail.com`, id 8) tam sedí přesně jako v produkční DB -
  tedy nejde jen o "soubor vznikl", ale o ověřený funkční restore.
  Vědomé omezení: zálohy jsou zatím jen lokální na droplet-u (chrání proti
  poškozené migraci/omylem smazaným datům, ne proti selhání celého disku/droplet-u)
  - offsite kopírování (DigitalOcean Spaces + rclone) je zdokumentované jako
  doporučený další krok v `DEPLOYMENT.md`, protože k reálnému Spaces účtu
  nemám přístup a nechtěl jsem psát netestovaný kód, který "vypadá hotově".
  Soubory: `docker-compose.yml`, `scripts/backup_db.sh` (nový),
  `scripts/restore_db.sh` (nový).

- [x] **K4 — Chybí HTTPS pro produkci**
  Řešení: `docker-compose.prod.yml` přidává `caddy` (image `caddy:2-alpine`)
  jako jediný vstup zvenku (80/443), terminuje TLS a proxuje na `frontend:80`
  přes interní síť - `Caddyfile` používá `{$DOMAIN}`/`{$ACME_EMAIL}` z `.env`.
  Frontend i backend přestaly publikovat porty v základním `docker-compose.yml`
  (přesunuto do `docker-compose.override.yaml`, čistě pro lokální dev).
  Nemůžu ověřit reálné vydání Let's Encrypt certifikátu bez veřejné domény a
  DNS (nemám k dispozici) - ověřil jsem ale celý mechanismus reálně: s
  `DOMAIN=localhost` Caddy automaticky (správně) pozná, že jde o neveřejný
  název, spadne na svoji vlastní lokálně-důvěryhodnou CA místo Let's Encrypt,
  a `curl https://localhost/` i `.../api/health` prošly s `200` včetně
  automatického HTTP→HTTPS redirectu (`308`). Stejný Caddyfile s reálnou
  doménou v `DOMAIN` použije Let's Encrypt - je to jen jiná větev stejné,
  Caddy-vlastní logiky autodetekce veřejná/neveřejná doména, ne kód, který
  bych psal a testoval poprvé. Přesný postup nasazení (DNS, firewall, `.env`,
  ověření že `issuer` v logu je `acme` ne `local`) je v `DEPLOYMENT.md`.
  Soubory: `Caddyfile` (nový), `docker-compose.prod.yml` (nový),
  `docker-compose.yml`, `docker-compose.override.yaml`, `.env.example`.

## DŮLEŽITÉ (před zákazníkem č. 5–10)

- [x] **D1 — Zpracování na pozadí bez retry/timeoutu/watchdogu**
  Řešení: nové sloupce `Invoice.processing_started_at`/`retry_count` (migrace
  `74d14ee849c1`). `pipeline.reap_stuck_invoices()` najde faktury v `processing`
  starší než `STUCK_PROCESSING_MINUTES` (default 10 min) - do `MAX_PROCESSING_RETRIES`
  (default 2) je vrátí na `uploaded` a nechá znovu zpracovat, po vyčerpání pokusů
  je označí `ocr_failed`. Spouští se z `app/main.py` (`_watchdog_loop`, asyncio
  task na startupu appky, žádná nová infra/závislost) každých `WATCHDOG_INTERVAL_SECONDS`
  (default 120s). Vědomě jednoduché řešení odpovídající velikosti appky (jeden
  proces) - reálná fronta (Celery/RQ) je další krok, až přibude zákazníků (viz
  DEPLOYMENT.md).
  Ověřeno živě dvakrát: (1) přímé volání `reap_stuck_invoices()` na uměle
  zaseklé faktuře - první průchod ji vrátil na `uploaded` s `retry_count=1`,
  po nastavení `retry_count=2` druhý průchod ji correctně poslal do `ocr_failed`;
  (2) integrační test celé smyčky se zkráceným intervalem (`WATCHDOG_INTERVAL_SECONDS=8`,
  `STUCK_PROCESSING_MINUTES=1`) - zaseklá faktura se skutečnou účtenkou na disku
  byla watchdogem nalezena, requeue-nuta A automaticky doopravdu zpracována
  (OCR+LLM) až do `needs_review` se správnými daty, bez jakéhokoliv ručního zásahu.
  Soubory: `app/models.py`, `alembic/versions/74d14ee849c1_*.py` (nový),
  `app/services/pipeline.py`, `app/main.py`.

- [x] **D5 — Chybí index na FK sloupcích (`customer_id`, `invoice_id`)**
  Řešení: `index=True` na obou sloupcích v `app/models.py`, promítnuto do stejné
  migrace `74d14ee849c1` jako D1 (`ix_invoices_customer_id`, `ix_line_items_invoice_id`).
  Ověřeno: `\d invoices` / `\d line_items` v produkční DB ukazují oba indexy.

- [x] **D2 — Špatná měna se zobrazí s vysokou jistotou (600× chyba beze stopy)**
  Řešení: nové pole `currency_confidence` (0.0-1.0) v LLM extrakci (`llm.py`) -
  prompt teď explicitně žádá nízkou hodnotu, když text neobsahuje žádnou stopu
  po měně a CZK je jen výchozí odhad. Uloženo na `Invoice.currency_confidence`
  (migrace `31240659a926`), v `InvoiceDetail.tsx` se pod stejným prahem 0.6
  jako u položek zobrazí ikona u částky + celý varovný banner s návodem, jak
  to opravit. Ruční oprava měny (`PATCH /invoices/{id}`) confidence resetuje
  na 1.0 - varování nezůstává viset po opravě.
  Ověřeno živě na PŘESNĚ té samé indonéské účtence z auditu (`receipt_00001.png`,
  ta s "91 000 CZK"): teď vrací `currency_confidence: 0.3`, tedy pod prahem -
  audit nález je teď viditelný, ne tichý. Po `PATCH {"currency":"IDR"}` se
  confidence potvrzeně vrátila na `1.0`.

- [x] **D3 — Zákazník nemůže v UI opravit dodavatele/datum**
  Řešení: `supplier_name` a `invoice_date` v `InvoiceDetail.tsx` teď taky
  `EditableCell` (backend už to podporoval, jen UI to neumožňovalo). Rozšířil
  jsem `EditableCell` o `displayValue`/`placeholder`/`className` a `type="date"`,
  aby šlo zobrazit hezčí formát ("Nerozpoznáno", formátované datum) bez rizika,
  že se ten popisek omylem uloží jako doslovná hodnota.
  Ověřeno: `tsc -b && vite build` prochází bez chyb (typová kontrola i produkční
  build), a `PATCH /invoices/{id}` s `supplier_name`/`invoice_date` funguje přes
  API přesně na stejné faktuře jako test D2 výše. Vizuální ověření v běžícím
  prohlížeči se bohužel nepodařilo dokončit - Chrome rozšíření pro browser
  automatizaci v tomto sezení opakovaně nereagovalo (zkoušeno 2×), takže UI
  je ověřené code-review + úspěšným buildem, ne živým kliknutím v prohlížeči.

- [x] **D4 — Upload: jen kontrola přípony, žádný limit frekvence/obsahu**
  Řešení: `python-magic` (+ `libmagic1` v Dockerfile) porovná skutečný obsah
  souboru (magic bytes) s deklarovanou příponou, ne jen s tím, co říká
  Content-Type/přípona - a `MAX_UPLOADS_PER_DAY` (default 300) omezuje počet
  nahraných souborů na zákazníka za 24h přes `Invoice.created_at`.
  Mimochodem opraveno i N1 (`os.path.basename()` na filename v `upload.py` i
  `customers.py` - viz audit, defense-in-depth i když dřív prakticky nešlo zneužít).
  Ověřeno živě: PNG přejmenovaný na `.pdf` → odmítnuto (`detected: image/png`);
  čistý text jako `.pdf` → odmítnuto (`detected: text/plain`, dřív by tohle
  prošlo); s `MAX_UPLOADS_PER_DAY=2` dočasně nastaveným přes `.env` - 1. soubor
  prošel, 2. a 3. v tom samém requestu správně odmítnuty s jasným důvodem.
  Soubory: `app/routers/upload.py`, `app/routers/customers.py`, `Dockerfile`,
  `pyproject.toml`, `.env.example`.

- [x] **D6 — Bezpečnostní položky nalezené navíc při opravách**
  Cílená druhá kontrola auth/upload/data handling (zadání bod 4), nad rámec
  věcí už řešených v K2/D4:
  - Nalezeno a opraveno rovnou v K2: backend port `8000` publikovaný v produkci
    (viz K2 výše).
  - Nalezeno a opraveno rovnou v D4: `os.path.basename()` na uploadech (N1).
  - Grep na nebezpečné vzory (`eval`, `exec`, `os.system`, `subprocess`,
    `pickle`, raw SQL string interpolace, hardcoded secrety) - čisté, nic
    nenalezeno. Veškerý DB přístup jde přes SQLAlchemy ORM s parametrizací.
  - JWT: `algorithms=[JWT_ALGORITHM]` explicitně v `decode()` - vyloučená
    "alg=none" obejití. Smazaný zákazník okamžitě přestane projít
    `get_current_customer` (kontrola existence v DB při každém requestu, ne
    jen podpis tokenu) - není problém s platnými tokeny po smazání účtu.
  - Frontend nikde nepoužívá `VITE_*`/`import.meta.env` proměnné - žádné
    riziko, že se tajemství omylem zabalí do klientského JS bundlu.
  - Zvážil jsem a VĚDOMĚ NEIMPLEMENTOVAL "Excel formula injection" sanitizaci
    (běžná položka bezpečnostních checklistů - řetězec začínající `=`/`+`/`-`/`@`
    v buňce). U pravého `.xlsx` psaného přes openpyxl (na rozdíl od `.csv`) má
    každá buňka v XML explicitní typ (řetězec/formule/číslo) - Excel string
    hodnotu nepřevyhodnocuje jako vzorec jen podle prvního znaku, to je čistě
    CSV problém. Přidat sem defenzivní escapování by jen kazilo legitimní data
    (např. popisky začínající pomlčkou) bez reálného bezpečnostního přínosu.

## NICE-TO-HAVE (udělám, pokud zbyde prostor)

- [x] N1 — `os.path.basename()` na nahrávaný filename (hotovo v rámci D4)
- [x] N2 — `/health` ověří i spojení na DB (hotovo mimochodem při D1 - `app/main.py`,
  `SELECT 1` přes vlastní DB session, `success:false`/`status:degraded` při výpadku)
- [x] N3 — Detekce duplicitního uploadu (hash souboru)
  Řešení: SHA-256 obsahu souboru do nového `Invoice.content_hash` (migrace
  `26c2f3ca067c`). Rozumný default: NEBLOKUJE upload (zákazník může chtít
  stejný scan nahrát znovu záměrně, např. po smazání omylem založené faktury) -
  jen v odpovědi přidá `duplicate_of_invoice_id`, frontend (`UploadButton.tsx`)
  to zobrazí jako informační poznámku pod tlačítkem.
  Ověřeno živě: 2× upload stejného souboru - druhý dostal vlastní `invoice_id`
  (nezablokováno) a `duplicate_of_invoice_id` ukazující na první. Přidán i
  pytest test (`test_duplicate_upload_is_flagged_but_not_blocked`) - 16/16 v CI sadě zelených.
  Soubory: `app/models.py`, `alembic/versions/26c2f3ca067c_*.py` (nový),
  `app/routers/upload.py`, `frontend/src/hooks/useUploadInvoices.ts`,
  `frontend/src/components/UploadButton.tsx`, `tests/test_upload_validation.py`.

- [ ] N4 — Drag & drop upload (nedoděláno, viz finální report - doporučení do budoucna)
- [x] N5 — Základní automatizované testy (pytest) + GitHub Actions CI
  Řešení: `tests/` pokrývá přesně to, co tenhle audit opravoval a kde by tichá
  regrese příště bolela nejvíc - auth + rate limiting (K2), multi-tenant
  izolace (IDOR, aktivně testováno v auditu), upload validace (D4, včetně
  přesně toho scénáře z auditu - .txt přejmenovaný na .pdf). OCR/LLM se v
  testech nevolá (`process_invoice` je pro test klienta monkeypatchnutý na
  no-op) - testy míří na validaci/autorizaci, ne na přesnost extrakce, a
  neběží proti reálnému Groq API ani Tesseractu. Testovací DB je SQLite
  soubor (ne produkční Postgres) - pro test fixtures to stačí a nepotřebuje to
  žádnou infrastrukturu navíc.
  `.github/workflows/ci.yml` staví STEJNÝ Dockerfile, co jde do produkce, a
  pytest pouští uvnitř něj (`--entrypoint sh`, SQLite místo Postgres) - žádné
  riziko, že CI běží na jiné sadě systémových závislostí (Tesseract, libmagic)
  než produkce. `pytest`/`httpx` jsou v `pyproject.toml` jako `[project.optional-dependencies].dev`,
  takže produkční image (`uv pip install --system -r pyproject.toml`) se o
  ně nezvětší.
  Mimochodem opraveno: `@app.on_event("startup")` (deprecated) nahrazeno
  moderním `lifespan` context managerem - stejná funkce (watchdog task),
  žádný deprecation warning navíc, ověřeno živě že appka dál startuje stejně.
  Ověřeno: `docker build` + spuštění `pytest tests/ -v` uvnitř zbuild-ované
  image → 15/15 testů zelených. Živý dev stack po refaktoru lifespan restartován
  a `/health` dál vrací `200`.
  Soubory: `tests/` (nový - `conftest.py`, `test_auth.py`, `test_authorization.py`,
  `test_upload_validation.py`), `.github/workflows/ci.yml` (nový),
  `pyproject.toml`, `app/main.py`.

- [x] N6 — `eval.py` na testovací sadu v `image/` (SPEC §12.2 kritérium)
  Řešení: `eval.py` v rootu projektu spustí `extract_text_from_file` (jen OCR
  krok, žádné volání Groq/LLM - bez API nákladů, bez sítě) na celou sadu
  `image/*.png` a ověří SPEC.md §12.2 kritérium č. 2 ("OCR reálně vrací
  neprázdný text u >= 90 % testovací sady"), které do teď nešlo automatizovaně
  ověřit vůbec (SPEC na `eval.py` odkazuje, ale nikdy neexistoval).
  Ověřeno živě uvnitř kontejneru (`docker compose exec web python eval.py`)
  na celé sadě 100 účtenek: **100/100 (100 %)** vrátilo neprázdný OCR text za
  89.5s - kritérium je tedy nezávisle potvrzené, ne jen předpokládané.
  Vědomě NENÍ zapojené do CI (`.github/workflows/ci.yml`) - běh přes celou
  sadu trvá ~90s a je to diagnostický skript pro ruční spuštění, ne rychlý
  gate na každý PR.
  Soubor: `eval.py` (nový).

---

## Zpětná vazba od zákazníka po nasazení (druhé kolo)

Tři reálné problémy nahlášené po prvním použití appky se skutečnou fakturou -
vyřešeno stejným postupem (plán → oprava → živé ověření → test → commit).

- [x] **Součet po ruční opravě částky se "aktualizoval jen někde"**
  Kořenová příčina, dohledaná na zákazníkově vlastní faktuře (Alza.cz, id 61):
  `invoice.total_amount` se po `PATCH /items/{id}` s `amount` VŽDY přepočítal
  správně (to fungovalo už předtím) - ale `amount_without_vat`/`vat_rate` u
  upravené položky zůstaly z PŮVODNÍ částky. Rozpad DPH v UI ("Základ daně",
  "DPH 21 %") je pak matematicky konzistentní sám se sebou (proto to nespadlo
  na žádné validaci), ale vztažený ke starému číslu - u zákazníkovy faktury to
  vypadalo jako "DPH 21 %" == 812 Kč ze základu 386 Kč, tedy ve skutečnosti
  ~210 %. Řešení: `PATCH /items/{id}` teď při změně `amount` BEZ zároveň
  dodaného `amount_without_vat` obě pole vynuluje - stejná zásada jako u LLM
  extrakce ("nikdy nedopočítávej DPH, když si nejsi jistý"), radši ukázat
  prostý mezisoučet než klamavě přesné číslo. Pokud zákazník pošle obě pole
  najednou (vědomá kompletní oprava), nic se nemaže.
  Ověřeno živě (reprodukce přesně zákazníkovy situace: položka 69 Kč se
  vat_rate=21/amount_without_vat=57.02, PATCH na amount=800) i 2 novými
  pytest testy - `18/18 zelených`.
  Soubor: `app/routers/invoices.py`, `tests/test_line_item_updates.py` (nový).
  **Vedlejší zjištění:** zákazníkova položka "Doprava" s částkou 800 Kč byla
  jeho vlastní ruční úprava (`is_corrected=true` v DB) - originál faktury
  uvádí dopravu za 69 Kč a celkovou částku 467 Kč, ne 1 198 Kč. Stojí za to
  to zkontrolovat, jestli to byl záměr.

- [x] **Review obrazovka se sama neaktualizuje, dokud faktura běží zpracováním**
  Kořenová příčina: `useInvoices()` (seznam vlevo) už dřív pollovat uměl, ale
  `useInvoiceDetail()`/`useInvoiceItems()` (detail otevřené faktury) ne -
  jakmile OCR/LLM doběhlo, detail zůstal zamrzlý na starém stavu, dokud
  uživatel neklikl na jinou fakturu a zpět (nová `queryKey` vynutila fetch).
  Řešení: oba hooky teď pollují po 3s, dokud je faktura `uploaded`/`processing`
  - `useInvoiceDetail` podle vlastního staženého statusu, `useInvoiceItems`
  podle stavu předaného z `InvoiceDetail.tsx` (položky samy o sobě status nenesou).
  Ověřeno: TypeScript build i produkční Vite build bez chyb. Živé kliknutí v
  prohlížeči se znovu nepodařilo ověřit (Chrome automatizace stále nereaguje) -
  logika je stejná jako u již ověřeného `useInvoices()` pollingu, jen aplikovaná
  na zbylé dva hooky, které ho předtím neměly.
  Soubory: `frontend/src/hooks/useInvoiceDetail.ts`, `useInvoiceItems.ts`,
  `frontend/src/components/InvoiceDetail.tsx`.

- [x] **"OCR bylo před opravami přesnější"**
  Vyšetřeno empiricky, ne odhadem: stáhl jsem uložený `raw_ocr_text` zákazníkovy
  faktury (Alza.cz, id 61) a spustil extrakci se STARÝM promptem (před D2, git
  historie) i s NOVÝM, oba přímo proti Groq API na tom samém textu. Výsledek:
  oba vrátily STEJNÝCH 3 položek se správným součtem 467 Kč - jediný rozdíl
  mezi commity je přidané pole `currency_confidence` (potvrzeno `git diff`),
  nic v částech promptu pro popis/kategorii/DPH. Reálný rozdíl mezi jednotlivými
  běhy (jiné rozdělení popisu položky 2, jiná kategorie) je normální LLM
  nedeterminismus (`temperature=0.1`), ne regrese způsobená mými změnami -
  ověřeno tím, že i stejný (nový) prompt spuštěný dvakrát dává mírně odlišné,
  ale stejně platné výsledky.
  Přesto snížil `temperature` na `0.0` (bylo `0.1`) - extrakce strukturovaných
  dat není kreativní úkol, nulová teplota dělá výsledky mezi jednotlivými
  nahráními téhož typu dokladu předvídatelnější, bez rizika/nákladu.
  Soubor: `app/services/llm.py`.

## Bonus drobnost nalezená při závěrečné regresi

- [x] **Float precision artefakt v `total_amount`** (např. `343.50800000000004`
  místo `343.51`) - součty částek (`pipeline.py`, `PATCH /items/{id}`,
  `POST /invoices/merge`) teď procházejí přes `round(..., 2)`. Všimnuto při
  finálním regresním testu, oprava bez rizika (jen zaokrouhlení při zápisu),
  žádná migrace potřeba. Ověřeno na nově zpracované faktuře - čisté číslo bez
  artefaktu. Existující už uložené hodnoty se retroaktivně neopravují (kosmetika,
  ne chyba v datech).

## Log postupu

**Po dokončení KRITICKÉ sekce (K1–K4)** — regresní E2E test celého flow proti
běžícímu dev stacku (standardní `docker compose up`, ne prod overlay):
registrace → upload validní účtenky → `needs_review` se správnými daty →
export → validní `.xlsx`; prázdný soubor → `ocr_failed` bez pádu; `.exe` →
odmítnuto na uploadu; IDOR (cizí zákazník na cizí fakturu) → `404`. Vše
prošlo beze změny chování oproti stavu před opravami - kritické opravy
nic nerozbily. Testovací zákazníci/faktury po testu smazáni přes
`DELETE /customers/{id}` (cascade přes ORM, ne přímé SQL).

**Po dokončení DŮLEŽITÉ sekce (D1–D6)** — širší regresní test se 2 zákazníky
najednou (přesně scénář "více zákazníků/šablon" ze zadání):
- Zákazník A (`category_rules: materiál/nářadí/doprava`) a B (`kancelářské
  potřeby/software`) - upload u obou proběhl a extrakce použila SPRÁVNÉ,
  navzájem odlišné kategorie každého zákazníka (ověřeno v datech položek).
- Edge cases znovu: prázdný soubor teď `python-magic` odmítne SYNCHRONNĚ při
  uploadu (`detected: application/x-empty`) místo dřívějšího asynchronního
  `ocr_failed` po zpracování - vědomá a correctní změna chování z D4, ne
  regrese (rychlejší zpětná vazba uživateli, stejný výsledek "tohle nejde
  zpracovat"). Špatná přípona i podvržený obsah (.txt jako .pdf) → odmítnuto.
- Oprava položky (`PATCH /items/{id}`) přepočítala `total_amount`, export
  vrátil validní `.xlsx` s opravenou hodnotou.
- **Per-customer Excel šablona** (admin `POST /customers/{id}/template`):
  zákazníkovi A nahraná vlastní šablona s mapováním sloupců - jeho export
  skutečně použil TU šablonu se správnými hlavičkami a daty na správných
  pozicích; zákazník B (bez šablony) dostal beze změny výchozí report formát.
  Potvrzuje, že per-customer konfigurace (kategorie i šablony) funguje správně
  i po všech provedených změnách schématu/pipeline.
- IDOR znovu čistý, rate limiter na loginu znovu funkční (5×401 → 429).
- Jeden pozorovaný (ne nový, už dřív existující) jev: složitější účtenka se
  slevou/servisním poplatkem u zákazníka B skončila s `total_amount`
  vyplněným, ale bez jednotlivých položek (LLM nebyl schopný rozpad spolehlivě
  přiřadit) - to je existující, spec-souladné chování (`pipeline.py` fallback
  větev "nic se nevytěžilo jako položka"), ne bug způsobený mými změnami.
  Nešlo o citelnou regresi, appka nic nepředstírala a nepadla.
Testovací data opět kompletně smazána po testu.
