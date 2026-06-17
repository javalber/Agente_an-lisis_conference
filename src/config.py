"""Configuración central del pipeline.

Todo lo configurable vive aquí y se lee de variables de entorno (que en
GitHub Actions provienen de los Secrets). No hay valores sensibles hardcodeados.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


def _split_list(raw: str | None) -> list[str]:
    """Convierte 'a@x.com, b@y.com; c@z.com' en ['a@x.com','b@y.com','c@z.com']."""
    if not raw:
        return []
    return [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]


def _as_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class Settings:
    # --- Gmail ---
    gmail_user: str
    gmail_app_password: str
    sender_email: str          # remitente conocido a buscar
    recipients: list[str]      # destinatarios del correo de salida
    processed_label: str = "procesado"
    subject_prefix: str = "Resumen conference call –"

    imap_host: str = "imap.gmail.com"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465

    # --- Modelo de IA (independiente del proveedor) ---
    # En Fase 1 stub_mode=True: NO se contacta ninguna API.
    stub_mode: bool = True
    model_provider: str = "anthropic"
    model_name: str = "claude-sonnet-4-6"

    @classmethod
    def from_env(cls) -> "Settings":
        gmail_user = os.environ.get("GMAIL_USER", "").strip()
        gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

        missing = [
            name
            for name, value in (
                ("GMAIL_USER", gmail_user),
                ("GMAIL_APP_PASSWORD", gmail_app_password),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Faltan variables de entorno obligatorias: " + ", ".join(missing)
            )

        sender_email = os.environ.get("SENDER_EMAIL", "").strip() or gmail_user
        recipients = _split_list(os.environ.get("RECIPIENTS"))
        if not recipients:
            log.warning(
                "RECIPIENTS no definido; se usará GMAIL_USER como destinatario."
            )
            recipients = [gmail_user]

        return cls(
            gmail_user=gmail_user,
            gmail_app_password=gmail_app_password,
            sender_email=sender_email,
            recipients=recipients,
            processed_label=os.environ.get("PROCESSED_LABEL", "procesado").strip(),
            subject_prefix=os.environ.get(
                "SUBJECT_PREFIX", "Resumen conference call –"
            ).strip(),
            stub_mode=_as_bool(os.environ.get("STUB_MODE"), default=True),
            model_provider=os.environ.get("MODEL_PROVIDER", "anthropic").strip(),
            model_name=os.environ.get("MODEL_NAME", "claude-sonnet-4-6").strip(),
        )
