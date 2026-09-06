FROM python:3.11-slim

WORKDIR /app

# Základní systémové závislosti
# - tesseract-ocr + tesseract-ocr-ces: OCR binárka a český jazykový balíček
# - poppler-utils: potřebuje pdf2image pro převod PDF -> obrázek
# - libgl1/libglib2.0-0: rapidocr-onnxruntime si vynucuje plnou (ne headless)
#   verzi opencv-python, která importuje libGL i v serverovém prostředí
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-ces \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Ověření, že OCR binárka je reálně funkční a obsahuje český jazykový model
# (podle SPEC.md se na to nesmí jen "spoléhat" - build musí selhat, pokud chybí).
RUN tesseract --version && tesseract --list-langs 2>&1 | grep -qx "ces"

# Instalace rychlého správce balíčků uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Zkopírujeme konfigurační soubor závislostí
COPY pyproject.toml ./

# Nainstaluje balíčky globálně do kontejneru
RUN uv pip install --system -r pyproject.toml

# Zkopírujeme zbytek kódu aplikace
COPY . .

RUN chmod +x /app/entrypoint.sh

# Neběžet jako root - appuser vlastní kód aplikace. Runtime adresáře pro
# uploads/exports/excel_templates se vytváří a chown-ují znovu v entrypoint.sh
# při každém startu: jde o cíle named volumes (viz docker-compose.yml), které
# Docker při prvním připojení prázdného volume vytvoří jako root, pokud na té
# cestě v obrazu předtím nic nebylo (PROGRESS.md K1) - spoléhat jen na tenhle
# build-time chown by pro named volumes nefungovalo spolehlivě.
RUN useradd -m appuser && chown -R appuser:appuser /app
RUN mkdir -p /app/uploads /app/exports /app/excel_templates && \
    chown -R appuser:appuser /app/uploads /app/exports /app/excel_templates

# Kontejner startuje jako root - entrypoint.sh opraví vlastnictví volumes a
# pak přes setpriv trvale přepne na appuser, než spustí aplikaci samotnou.
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
