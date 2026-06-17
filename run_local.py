"""Modo de prueba LOCAL (sin GitHub Actions).

- Carga variables desde un archivo `.env`.
- FUERZA STUB_MODE=true (resúmenes falsos, NO se contacta ningún modelo).
- FUERZA que el correo se envíe SOLO a ti mismo (GMAIL_USER), ignorando
  RECIPIENTS, para que puedas verificar de punta a punta sin molestar a nadie.

Uso:
    cp .env.example .env   # y rellena tus credenciales
    python run_local.py

Flags:
    --real-recipients   No sobreescribe RECIPIENTS (envía a la lista real).
"""

from __future__ import annotations

import argparse
import logging

from dotenv import load_dotenv

from src.config import Settings
from src.pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba local del pipeline (stub).")
    parser.add_argument(
        "--real-recipients",
        action="store_true",
        help="Enviar a RECIPIENTS reales en lugar de solo a ti mismo.",
    )
    args = parser.parse_args()

    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("run_local")

    settings = Settings.from_env()

    # Fase 1: nunca tocar el modelo en pruebas locales.
    settings.stub_mode = True

    if not args.real_recipients:
        settings.recipients = [settings.gmail_user]
        log.info("Modo prueba: el correo se enviará SOLO a %s", settings.gmail_user)

    log.info(
        "STUB_MODE=%s | remitente buscado=%s | etiqueta=%s",
        settings.stub_mode,
        settings.sender_email,
        settings.processed_label,
    )
    sent = run(settings)
    log.info("Finalizado. Enviados: %d", sent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
