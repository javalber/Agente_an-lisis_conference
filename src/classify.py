"""Clasificación de adjuntos por NOMBRE de archivo — código determinista.

El remitente real envía los documentos duplicados en inglés y español, y la
"presentación" llega como PDF (no PPTX). Por eso no basta con la extensión:

  - `kind`     -> cómo EXTRAER el texto (pdf | excel | pptx | unknown).
  - `role`     -> qué PLANTILLA de resumen aplicar
                  (presentation | report | excel | invitation | other).
  - `language` -> para elegir un idioma y no resumir dos veces lo mismo
                  (en | es | neutral).

Detección por palabras clave en el nombre; se chequea español primero porque
'reporte' contiene 'report' y 'presentación' es distinto de 'presentation'.
"""

from __future__ import annotations

import os
from typing import Literal, TypedDict

FileKind = Literal["excel", "pptx", "pdf", "unknown"]
Role = Literal["presentation", "report", "excel", "invitation", "other"]
Language = Literal["en", "es", "neutral"]

_EXT_TO_KIND: dict[str, FileKind] = {
    ".xlsx": "excel",
    ".xlsm": "excel",
    ".xls": "excel",
    ".pptx": "pptx",
    ".pdf": "pdf",
}


class Classification(TypedDict):
    kind: FileKind
    role: Role
    language: Language


def _kind(filename: str) -> FileKind:
    _, ext = os.path.splitext(filename.lower())
    return _EXT_TO_KIND.get(ext, "unknown")


def _role(lower: str, kind: FileKind) -> Role:
    if "invitaci" in lower or "invitation" in lower:
        return "invitation"
    if "presentaci" in lower or "presentation" in lower:
        return "presentation"
    if "report" in lower or "reporte" in lower:  # 'report' cubre también 'reporte'
        return "report"
    if kind == "excel":
        return "excel"
    return "other"


def _language(lower: str) -> Language:
    es_markers = ("3t", "invitaci", "presentaci", "reporte", "ó", "í", "á", "é")
    en_markers = ("3q", "invitation", "presentation", "report")
    if any(m in lower for m in es_markers):
        return "es"
    if any(m in lower for m in en_markers):
        return "en"
    return "neutral"


def classify(filename: str) -> Classification:
    lower = filename.lower()
    kind = _kind(filename)
    role = _role(lower, kind)
    # Los estados financieros (Excel) suelen ser únicos/bilingües -> neutral,
    # para que se incluyan sea cual sea el idioma elegido.
    language: Language = "neutral" if role == "excel" else _language(lower)
    return Classification(kind=kind, role=role, language=language)
