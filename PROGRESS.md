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

- [ ] **D4 — Upload: jen kontrola přípony, žádný limit frekvence/obsahu**
  Plán: `python-magic` kontrola skutečného typu souboru + denní limit počtu
  uploadů na zákazníka.

- [ ] **D6 — Bezpečnostní položky nalezené navíc při opravách**
  (doplním průběžně, pokud narazím — appka se prochází podruhé cíleně na
  auth/upload/data handling podle bodu 4 zadání)

## NICE-TO-HAVE (udělám, pokud zbyde prostor)

- [ ] N1 — `os.path.basename()` na nahrávaný filename (defense-in-depth)
- [x] N2 — `/health` ověří i spojení na DB (hotovo mimochodem při D1 - `app/main.py`,
  `SELECT 1` přes vlastní DB session, `success:false`/`status:degraded` při výpadku)
- [ ] N3 — Detekce duplicitního uploadu (hash souboru)
- [ ] N4 — Drag & drop upload
- [ ] N5 — Základní automatizované testy (pytest) + GitHub Actions CI
- [ ] N6 — `eval.py` na testovací sadu v `image/` (SPEC §12.2 kritérium)

---

## Log postupu

**Po dokončení KRITICKÉ sekce (K1–K4)** — regresní E2E test celého flow proti
běžícímu dev stacku (standardní `docker compose up`, ne prod overlay):
registrace → upload validní účtenky → `needs_review` se správnými daty →
export → validní `.xlsx`; prázdný soubor → `ocr_failed` bez pádu; `.exe` →
odmítnuto na uploadu; IDOR (cizí zákazník na cizí fakturu) → `404`. Vše
prošlo beze změny chování oproti stavu před opravami - kritické opravy
nic nerozbily. Testovací zákazníci/faktury po testu smazáni přes
`DELETE /customers/{id}` (cascade přes ORM, ne přímé SQL).
