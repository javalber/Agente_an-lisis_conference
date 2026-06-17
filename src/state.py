"""Tipos del estado que circula por el grafo LangGraph."""

from __future__ import annotations

from typing import Literal, Optional, TypedDict

# Tipo de archivo reconocido. 'unknown' se descarta en la ingesta.
FileKind = Literal["excel", "pptx", "pdf", "unknown"]


class Attachment(TypedDict):
    filename: str       # nombre original del adjunto
    path: str           # ruta local al archivo descargado (efímera)
    kind: FileKind      # excel | pptx | pdf
    text: str           # texto plano extraído (lo llena el nodo 'extract')
    summary: str        # resumen por archivo (lo llena el nodo 'summarize')


class PipelineState(TypedDict):
    uid: str                       # UID IMAP del correo de origen
    subject: str                   # asunto del correo de origen
    attachments: list[Attachment]
    email_body: str                # cuerpo redactado (lo llena el nodo 'draft')
    sent: bool                     # True solo si SMTP tuvo éxito
    error: Optional[str]           # detalle del fallo, si lo hubo
