"""Tipos del estado que circula por el grafo LangGraph."""

from __future__ import annotations

from typing import Optional, TypedDict

from .classify import FileKind, Language, Role


class Attachment(TypedDict):
    filename: str       # nombre original del adjunto
    path: str           # ruta local al archivo descargado (efímera)
    kind: FileKind      # cómo extraer texto: excel | pptx | pdf
    role: Role          # qué plantilla de resumen: presentation | report | excel | ...
    language: Language  # en | es | neutral (para elegir idioma)
    text: str           # texto plano extraído (lo llena el nodo 'extract')
    summary: str        # resumen por archivo (lo llena el nodo 'summarize')


class PipelineState(TypedDict):
    uid: str                       # UID IMAP del correo de origen
    subject: str                   # asunto del correo de origen
    attachments: list[Attachment]  # TODOS los descargados (para reenviar)
    to_summarize: list[Attachment] # subconjunto seleccionado (idioma/rol)
    email_body: str                # cuerpo redactado (lo llena el nodo 'draft')
    sent: bool                     # True solo si SMTP tuvo éxito
    error: Optional[str]           # detalle del fallo, si lo hubo
