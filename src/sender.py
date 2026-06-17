"""Envío de correo por SMTP con adjuntos — código determinista (NO usa modelo)."""

from __future__ import annotations

import logging
import mimetypes
import os
import smtplib
import ssl
from email.message import EmailMessage

from .config import Settings

log = logging.getLogger(__name__)


def send_email(
    settings: Settings,
    subject: str,
    body: str,
    attachment_paths: list[str],
) -> None:
    """Envía el correo de resumen desde el Gmail configurado, adjuntando los
    archivos originales. Lanza excepción si algo falla (para que el correo de
    origen NO se marque como procesado)."""
    msg = EmailMessage()
    msg["From"] = settings.gmail_user
    msg["To"] = ", ".join(settings.recipients)
    msg["Subject"] = subject
    msg.set_content(body)

    for path in attachment_paths:
        ctype, _ = mimetypes.guess_type(path)
        maintype, _, subtype = (ctype or "application/octet-stream").partition("/")
        with open(path, "rb") as fh:
            msg.add_attachment(
                fh.read(),
                maintype=maintype,
                subtype=subtype or "octet-stream",
                filename=os.path.basename(path),
            )

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context) as server:
        server.login(settings.gmail_user, settings.gmail_app_password)
        server.send_message(msg)

    log.info(
        "Correo enviado a %s con %d adjunto(s).",
        settings.recipients,
        len(attachment_paths),
    )