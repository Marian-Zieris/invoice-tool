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

- [ ] **K2 — Bez rate limitu na `/auth/login` (brute force)**
  Plán: jednoduchý in-memory per-IP+email sliding-window limiter (bez Redis,
  odpovídá velikosti appky) na `/auth/login`. Zalogovat i zamítnuté pokusy.

- [ ] **K3 — Žádné zálohování dat**
  Plán: skript `scripts/backup_db.sh` (pg_dump + gzip, rotace starých záloh),
  volitelně i zálohu `uploads/`. Spustitelný z cronu na produkčním droplet-u,
  zdokumentovaný v deployment checklistu (vč. volitelného odesílání do
  DigitalOcean Spaces přes `rclone`/`s3cmd`, protože k reálnému object storage
  účtu nemám přístup).

- [ ] **K4 — Chybí HTTPS pro produkci**
  Plán: přidat produkční Caddy reverse-proxy (automatický Let's Encrypt) jako
  alternativu/nahrazení nginx pro nasazení na doméně, `docker-compose.prod.yml`
  override. Nemůžu vydat reálný certifikát bez domény/veřejné IP — připravím
  konfiguraci a zdokumentuji přesné kroky pro drople.

## DŮLEŽITÉ (před zákazníkem č. 5–10)

- [ ] **D1 — Zpracování na pozadí bez retry/timeoutu/watchdogu**
  Plán: přidat `Invoice.processing_started_at`, watchdog funkci volanou
  periodicky (APScheduler nebo jednoduchý background loop při startu appky),
  která fakturu zaseklou v `processing` déle než N minut vrátí zpět ke zpracování
  (s omezeným počtem pokusů) nebo označí jako `ocr_failed`.

- [ ] **D2 — Špatná měna se zobrazí s vysokou jistotou (600× chyba beze stopy)**
  Plán: LLM prompt rozšířit o `currency_confidence`, uložit na `Invoice`,
  v UI zvýraznit stejně jako nízkou jistotu položky.

- [ ] **D3 — Zákazník nemůže v UI opravit dodavatele/datum**
  Plán: obalit `supplier_name` a `invoice_date` v `InvoiceDetail.tsx` do
  `EditableCell`, stejně jako už funguje měna.

- [ ] **D4 — Upload: jen kontrola přípony, žádný limit frekvence/obsahu**
  Plán: `python-magic` kontrola skutečného typu souboru + denní limit počtu
  uploadů na zákazníka.

- [ ] **D5 — Chybí index na FK sloupcích (`customer_id`, `invoice_id`)**
  Plán: nová Alembic migrace, `CREATE INDEX` na obou sloupcích.

- [ ] **D6 — Bezpečnostní položky nalezené navíc při opravách**
  (doplním průběžně, pokud narazím — appka se prochází podruhé cíleně na
  auth/upload/data handling podle bodu 4 zadání)

## NICE-TO-HAVE (udělám, pokud zbyde prostor)

- [ ] N1 — `os.path.basename()` na nahrávaný filename (defense-in-depth)
- [ ] N2 — `/health` ověří i spojení na DB
- [ ] N3 — Detekce duplicitního uploadu (hash souboru)
- [ ] N4 — Drag & drop upload
- [ ] N5 — Základní automatizované testy (pytest) + GitHub Actions CI
- [ ] N6 — `eval.py` na testovací sadu v `image/` (SPEC §12.2 kritérium)

---

## Log postupu

(doplňováno průběžně)
