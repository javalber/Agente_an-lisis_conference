"""Punto de entrada para GitHub Actions (y para correr en producción).

Lee toda la configuración de variables de entorno (Secrets en Actions) y
ejecuta el pipeline. Respeta STUB_MODE: en Fase 1 debe estar en 'true'.
"""

from __future__ import annotations

import logging
import sys

from src.pipeline import run


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    _setup_logging()
    sent = run()  # Settings.from_env()
    logging.getLogger("main").info("Finalizado. Enviados: %d", sent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
