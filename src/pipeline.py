"""Orquestador de alto nivel: busca correos, descarga adjuntos y corre el grafo
para cada uno. Es el punto de entrada que invoca tanto GitHub Actions como el
modo de prueba local.
"""

from __future__ import annotations

import logging
import tempfile

from .config import Settings
from .gmail_ingest import GmailClient
from .graph import build_graph

log = logging.getLogger(__name__)


def _select_to_summarize(attachments: list, settings: Settings) -> list:
    """Filtra los adjuntos a resumir por rol e idioma. Los 'neutral' (p. ej.
    el Excel de estados financieros) se incluyen sea cual sea el idioma."""
    roles = set(settings.summarize_roles)
    lang = settings.summarize_language
    return [
        a for a in attachments
        if a["role"] in roles and a["language"] in (lang, "neutral")
    ]


def run(settings: Settings | None = None) -> int:
    """Procesa todos los correos pendientes. Devuelve cuántos se enviaron OK.

    Cada correo se procesa de forma aislada: si la extracción, el modelo o el
    SMTP fallan, ese correo NO se marca como procesado y se reintentará en la
    siguiente corrida; los demás continúan.
    """
    settings = settings or Settings.from_env()
    client = GmailClient(settings)
    graph = build_graph(settings, client)

    uids = client.search_unprocessed()
    if not uids:
        log.info("No hay correos pendientes. Nada que hacer.")
        return 0

    sent_count = 0
    for uid in uids:
        with tempfile.TemporaryDirectory(prefix="conf_call_") as tmp:
            try:
                subject, attachments = client.download_attachments(uid, tmp)

                if not attachments:
                    log.warning(
                        "UID %s: sin adjuntos reconocidos (Excel/PPTX/PDF). Se omite.",
                        uid,
                    )
                    continue

                log.info(
                    "UID %s: %d adjunto(s): %s",
                    uid, len(attachments), [a["filename"] for a in attachments],
                )

                to_summarize = _select_to_summarize(attachments, settings)
                if not to_summarize:
                    log.warning(
                        "UID %s: ningún adjunto coincide con roles=%s e idioma=%s. "
                        "Se omite (no se marca).",
                        uid, settings.summarize_roles, settings.summarize_language,
                    )
                    continue
                log.info(
                    "UID %s: se resumirán %d documento(s): %s",
                    uid, len(to_summarize), [a["filename"] for a in to_summarize],
                )

                state = {
                    "uid": uid,
                    "subject": subject,
                    "attachments": attachments,
                    "to_summarize": to_summarize,
                    "email_body": "",
                    "sent": False,
                    "error": None,
                }
                result = graph.invoke(state)

                if result.get("sent"):
                    sent_count += 1
                    log.info("UID %s: enviado y marcado como procesado.", uid)
                else:
                    log.error(
                        "UID %s: NO enviado (%s). No se marca como procesado.",
                        uid,
                        result.get("error"),
                    )
            except Exception:  # noqa: BLE001 - aislamos el fallo por correo
                log.exception(
                    "UID %s: error no controlado. No se marca; se reintentará.", uid
                )

    log.info("Resumen: %d/%d correo(s) enviado(s) con éxito.", sent_count, len(uids))
    return sent_count
