# Nasazení na DigitalOcean — checklist

Cílový stav: droplet s Dockerem, appka dostupná přes HTTPS na vlastní doméně,
zálohovaná, bez zbytečně otevřených portů.

## 1. Droplet a DNS

1. Droplet (stačí nejmenší s 2 GB RAM kvůli RapidOCR/Tesseract — 1 GB často nestačí).
2. Nainstalovat Docker + Compose plugin (`curl -fsSL https://get.docker.com | sh`).
3. A záznam domény (např. `faktury.tvoje-firma.cz`) → veřejná IP droplet-u.
   Bez tohohle Caddy nezíská certifikát — ACME ověření probíhá přes tuhle IP.
4. Firewall (`ufw` nebo DO Cloud Firewall): povolit jen **80, 443, 22**.
   Porty 5432 (DB) a 8000 (backend) se v produkční konfiguraci vůbec
   nepublikují ven (viz `docker-compose.yml` — `ports` je jen v
   `docker-compose.override.yaml`, který se do produkce nepoužívá), takže
   není co blokovat navíc, ale nezapomeň to při ladění na droplet-u zase
   ručně needitovat zpátky.

## 2. `.env`

Zkopírovat `.env.example` → `.env` a vyplnit **skutečné** hodnoty:

- `POSTGRES_PASSWORD`, `SECRET_KEY`, `ADMIN_API_KEY` — vygenerovat nové
  (`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`), ne
  zkopírovat z dev prostředí.
- `GROQ_KEY` — reálný produkční klíč.
- `DOMAIN` — skutečná doména z kroku 1 (ne `localhost`).
- `ACME_EMAIL` — e-mail, kam Let's Encrypt posílá upozornění na expiraci/problémy.
- `BACKUP_KEEP_DAYS` — kolik dní držet lokální zálohy (výchozí 14 je rozumné minimum).

`.env` se negituje (`.gitignore`) — přenést na droplet ručně/přes tajný kanál,
nikdy přes commit.

## 3. Start

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

**Nepoužívat** `docker-compose.override.yaml` v produkci — obsahuje dev věci
(`--reload`, bind mount kódu, publikované porty DB/backendu). Compose ho bere
automaticky JEN když spustíš `docker compose up` bez explicitních `-f` — jakmile
uvedeš `-f docker-compose.yml -f docker-compose.prod.yml`, override se nepoužije.

Migrace (`alembic upgrade head`) se spustí sama jako součást startu `web`
kontejneru (`entrypoint.sh`) — není potřeba nic pouštět ručně.

## 4. Ověření po nasazení

```sh
docker logs invoice_caddy | grep "certificate obtained"
# musí obsahovat "issuer":"acme" (Let's Encrypt), NE "issuer":"local"
# ("local" = Caddy nepoznal DOMAIN jako veřejnou doménu - zkontroluj DNS)

curl -I https://tvoje-domena.cz/          # očekávej 200
curl https://tvoje-domena.cz/api/health   # {"success":true,...}
```

Pak proveď ruční smoke test stejný jako v auditu: registrace zákazníka (přes
`X-Admin-Key`), upload faktury, počkat na `needs_review`, export do Excelu.

## 5. Zálohy

Zálohovací služba (`backup` v `docker-compose.yml`) běží automaticky, jednou
denně dumpne DB do named volume `db_backups` a maže starší než
`BACKUP_KEEP_DAYS`. To chrání proti špatné migraci/omylem smazaným datům, ale
**ne** proti ztrátě/výpadku celého droplet-u — zálohy zatím sedí na stejném
disku jako produkční data.

**Doporučený další krok** (zatím neimplementováno — vyžaduje reálný účet):
kopírovat obsah `db_backups` volume i mimo droplet, např. do DigitalOcean
Spaces přes `rclone`:

```sh
# jednorázově na droplet-u: rclone config (nastavit remote "do-spaces")
docker run --rm -v invoice-tool_db_backups:/backups:ro -v ~/.config/rclone:/root/.config/rclone rclone/rclone \
  sync /backups do-spaces:tvuj-bucket/invoice-backups
```
Přidat jako denní cron na hostiteli, dokud se to nezautomatizuje přímo do
`backup` služby.

### Test obnovy (udělat aspoň jednou po nasazení, ne až při skutečné nehodě)

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backup \
  sh /scripts/restore_db.sh /backups/invoices_XXXXXXXX_XXXXXX.sql.gz
```
Restore přepisuje aktuální databázi — appku (`web`) předtím zastavit.
Ověřeno funkční na tomto repu (viz PROGRESS.md K3) proti testovací DB, ne
proti produkčním datům — na droplet-u si to i tak vyzkoušej se zálohou, která
nikoho nebolí.

## 6. Rutinní provoz

- Nový build po změně kódu: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.
- Logy: `docker compose logs -f web` / `caddy` / `backup`.
- Zákazníky zatím zakládáš ty sám přes `POST /customers` s `X-Admin-Key`
  (self-service registrace vědomě není v MVP — viz SPEC.md).

## 7. Co ještě stojí za zvážení, než přijde víc zákazníků

Viz `PROGRESS.md`, sekce Důležité/Nice-to-have — hlavně fronta na zpracování
(D1) a offsite zálohy (bod 5 výše), jakmile bude víc než 1-2 zákazníků.
