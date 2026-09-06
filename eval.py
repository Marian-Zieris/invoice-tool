#!/usr/bin/env python3
"""Ověří SPEC.md §12.2 kritérium č. 2: OCR musí reálně vrátit neprázdný text
u >= 90 % testovací sady (image/*.png|*.jpg|*.pdf) - NE fallback/mock data.

Neváže se na Groq/LLM (žádné API náklady, žádná síť) - jen na samotný
OCR krok (Tesseract/RapidOCR), přesně tu část pipeline, které se kritérium
týká. Spouštět uvnitř image, kde jsou nainstalované systémové OCR závislosti:

    docker compose exec web python eval.py
    # nebo mimo běžící kontejner:
    docker run --rm -v "$(pwd)/image:/app/image:ro" --entrypoint python invoice-tool-web eval.py
"""

import sys
import time
from pathlib import Path

from app.services.ocr import extract_text_from_file

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".pdf"}
REQUIRED_SUCCESS_RATE = 0.90


def main() -> int:
    dataset_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "image"
    files = sorted(p for p in dataset_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS)

    if not files:
        print(f"Žádné soubory k otestování v {dataset_dir}")
        return 1

    failures = []
    started = time.monotonic()

    for path in files:
        try:
            text = extract_text_from_file(str(path))
        except Exception as exc:  # noqa: BLE001 - chceme pokračovat i po chybě na jednom souboru
            failures.append((path.name, f"exception: {exc}"))
            continue
        if not text.strip():
            failures.append((path.name, "prázdný OCR výstup"))

    elapsed = time.monotonic() - started
    total = len(files)
    success = total - len(failures)
    success_rate = success / total

    print(f"OCR: {success}/{total} souborů vrátilo neprázdný text ({success_rate:.1%}) za {elapsed:.1f}s")
    if failures:
        print("\nSelhalo:")
        for name, reason in failures:
            print(f"  - {name}: {reason}")

    if success_rate >= REQUIRED_SUCCESS_RATE:
        print(f"\nOK - splňuje kritérium SPEC.md §12.2 (>= {REQUIRED_SUCCESS_RATE:.0%}).")
        return 0

    print(f"\nNESPLNĚNO - SPEC.md §12.2 vyžaduje >= {REQUIRED_SUCCESS_RATE:.0%}.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
