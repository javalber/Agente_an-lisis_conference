"""Ingesta de Gmail por IMAP — código determinista (NO usa modelo).

Responsabilidades:
  - Buscar correos del remitente conocido que aún no tengan la etiqueta de
    procesado (usando la búsqueda nativa de Gmail vía X-GM-RAW).
  - Descargar los adjuntos reconocidos (Excel / PPTX / PDF) de un correo.
  - Aplicar la etiqueta de procesado a un correo (SOLO se llama tras envío OK).

El estado vive en Gmail (la etiqueta), no en disco, porque el runner de
GitHub Actions es efímero.
"""

from __future__ import annotations

import email
import imaplib
import logging
import os
from email.header import decode_header
from email.message import Message

from .config import Settings
from .state import Attachment, FileKind

log = logging.getLogger(__name__)

# Extensión -> tipo lógico de archivo.
_EXT_TO_KIND: dict[str, FileKind] = {
    ".xlsx": "excel",
    ".xlsm": "excel",
    ".xls": "excel",
    ".pptx": "pptx",
    ".pdf": "pdf",
}


def classify(filename: str) -> FileKind:
    _, ext = os.path.splitext(filename.lower())
    return _EXT_TO_KIND.get(ext, "unknown")


def _decode_mime(value: str | None) -> str:
    """Decodifica encabezados/nombres de archivo MIME (=?utf-8?...?=)."""
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


class GmailClient:
    """Cliente IMAP fino para Gmail. Abre/cierra conexión por operación
    (volumen bajo, runner efímero -> simple y robusto)."""

    def __init__(self, settings: Settings):
        self.s = settings

    def _connect(self) -> imaplib.IMAP4_SSL:
        imap = imaplib.IMAP4_SSL(self.s.imap_host)
        imap.login(self.s.gmail_user, self.s.gmail_app_password)
        return imap

    # -- Búsqueda --------------------------------------------------------

    def search_unprocessed(self) -> list[str]:
        """Devuelve los UID de correos del remitente, con adjuntos y SIN la
        etiqueta de procesado. Usa la sintaxis de búsqueda de Gmail (X-GM-RAW)."""
        imap = self._connect()
        try:
            imap.select("INBOX")
            query = (
                f'from:{self.s.sender_email} '
                f'has:attachment '
                f'-label:{self.s.processed_label}'
            )
            typ, data = imap.uid("SEARCH", None, "X-GM-RAW", f'"{query}"')
            if typ != "OK":
                raise RuntimeError(f"Fallo en búsqueda IMAP: {typ} {data!r}")
            raw = data[0] or b""
            uids = [u.decode() for u in raw.split()]
            log.info("Búsqueda Gmail [%s] -> %d correo(s).", query, len(uids))
            return uids
        finally:
            try:
                imap.logout()
            except Exception:  # noqa: BLE001 - logout best-effort
                pass

    # -- Descarga de adjuntos -------------------------------------------

    def download_attachments(
        self, uid: str, dest_dir: str
    ) -> tuple[str, list[Attachment]]:
        """Descarga los adjuntos reconocidos del correo `uid` a `dest_dir`.

        Devuelve (asunto, lista de Attachment). Usa BODY.PEEK para no marcar
        el correo como leído.
        """
        imap = self._connect()
        try:
            imap.select("INBOX")
            typ, data = imap.uid("FETCH", uid, "(BODY.PEEK[])")
            if typ != "OK" or not data or data[0] is None:
                raise RuntimeError(f"No se pudo descargar el correo UID {uid}: {typ}")

            raw_bytes = data[0][1]
            msg: Message = email.message_from_bytes(raw_bytes)
            subject = _decode_mime(msg.get("Subject")) or "(sin asunto)"

            attachments: list[Attachment] = []
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                filename = _decode_mime(part.get_filename())
                if not filename:
                    continue
                kind = classify(filename)
                if kind == "unknown":
                    log.debug("UID %s: se ignora adjunto no soportado %s", uid, filename)
                    continue

                payload = part.get_payload(decode=True)
                if payload is None:
                    log.warning("UID %s: adjunto %s sin payload, se omite.", uid, filename)
                    continue

                path = os.path.join(dest_dir, filename)
                with open(path, "wb") as fh:
                    fh.write(payload)
                attachments.append(
                    Attachment(
                        filename=filename,
                        path=path,
                        kind=kind,
                        text="",
                        summary="",
                    )
                )
                log.info("UID %s: descargado %s (%s)", uid, filename, kind)

            return subject, attachments
        finally:
            try:
                imap.logout()
            except Exception:  # noqa: BLE001
                pass

    # -- Marcar como procesado ------------------------------------------

    def mark_processed(self, uid: str) -> None:
        """Aplica la etiqueta de procesado al correo. Gmail crea la etiqueta
        automáticamente si no existe. SOLO debe llamarse tras un envío exitoso."""
        imap = self._connect()
        try:
            imap.select("INBOX")
            # Si la etiqueta tiene espacios, va entre comillas.
            label = self.s.processed_label
            label_arg = f'"{label}"' if " " in label else label
            typ, resp = imap.uid("STORE", uid, "+X-GM-LABELS", label_arg)
            if typ != "OK":
                raise RuntimeError(
                    f"No se pudo etiquetar UID {uid} como '{label}': {typ} {resp!r}"
                )
            log.info("UID %s etiquetado como '%s'.", uid, label)
        finally:
            try:
                imap.logout()
            except Exception:  # noqa: BLE001
                pass