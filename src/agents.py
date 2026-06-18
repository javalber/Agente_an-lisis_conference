"""Los DOS únicos puntos que (en Fase 3) invocan un modelo de IA:

  (a) summarize_attachment  -> resumen de cada archivo.
  (b) draft_email           -> redacción del correo con los tres resúmenes.

Independencia del proveedor: el modelo se resuelve SIEMPRE vía
`init_chat_model` de LangChain, usando MODEL_PROVIDER / MODEL_NAME. La lógica
de los nodos no conoce el proveedor.

FASE 1: `settings.stub_mode` es True -> se devuelven resúmenes FALSOS y NO se
contacta ninguna API. La rama real (stub_mode=False) ya está escrita pero queda
DORMIDA hasta la Fase 3 (basta poner STUB_MODE=false y la API key).
"""

from __future__ import annotations

import logging
import re

from .config import Settings
from .prompts import (
    DEFAULT_SUMMARY_PROMPT,
    EMAIL_PROMPT,
    EXCEL_REDUCE_PROMPT,
    SUMMARY_PROMPTS,
)
from .state import Attachment

log = logging.getLogger(__name__)


def _get_chat_model(settings: Settings):
    """Resuelve el chat model de forma agnóstica al proveedor.

    Import perezoso: en Fase 1 (stub) no se requiere langchain instalado/ni API.
    """
    from langchain.chat_models import init_chat_model

    return init_chat_model(
        model=settings.model_name,
        model_provider=settings.model_provider,
    )


# Tokens de trimestre tipo 1Q26 / 4Q25 / 1T26 (Q inglés o T español).
_QUARTER_RE = re.compile(r"\b([1-4])\s*[QT]\s*(\d{2})\b", re.IGNORECASE)


def _max_quarter(text: str) -> str | None:
    """Devuelve el trimestre de mayor (año, Q) hallado por regex, p. ej. '1Q26'."""
    best_key = None
    best_label = None
    for m in _QUARTER_RE.finditer(text):
        quarter, year = int(m.group(1)), int(m.group(2)) % 100
        key = (year, quarter)
        if best_key is None or key > best_key:
            best_key, best_label = key, f"{m.group(1)}Q{year:02d}"
    return best_label


def _filename_period(filename: str) -> str | None:
    """Período indicado por el NOMBRE del archivo, p. ej. 'grupo-aval-...-1q-26.xlsx'
    -> '1Q26'. Acepta separadores (1q-26, 1q26, 1q2026)."""
    m = re.search(r"([1-4])\s*[QT]\s*[-_ ]?\s*(\d{2,4})", filename, re.IGNORECASE)
    if not m:
        return None
    return f"{m.group(1)}Q{int(m.group(2)) % 100:02d}"


def _period_header_lines(text: str, limit: int = 40) -> str:
    """Solo las líneas que contienen etiquetas de período (encabezados), para
    pasarle al modelo un contexto MÍNIMO y barato (no todo el archivo)."""
    seen: list[str] = []
    for line in text.splitlines():
        if _QUARTER_RE.search(line) and line not in seen:
            seen.append(line.strip()[:400])
        if len(seen) >= limit:
            break
    return "\n".join(seen)


def _detect_latest_period(att: Attachment, model) -> str | None:
    """Verificación LIGERA con el modelo del período más reciente del Excel.

    No asume el orden de las columnas (en US GAAP a veces el período actual va
    primero). Usa como contexto solo el nombre del archivo + las filas de
    encabezados. Si el modelo falla o no hay encabezados, cae a un prior
    determinista (nombre de archivo, luego máximo por regex)."""
    prior = _filename_period(att["filename"]) or _max_quarter(att["text"])
    headers = _period_header_lines(att["text"])
    if not headers:
        return prior

    prompt = (
        "Tu única tarea es identificar el PERÍODO de reporte MÁS RECIENTE de un "
        "archivo financiero. Las columnas pueden estar en orden ascendente o "
        "descendente; el más reciente NO es necesariamente el último.\n"
        f"Nombre del archivo: {att['filename']}\n"
        f"Filas de encabezados de las tablas:\n{headers}\n\n"
        "Responde SOLO con la etiqueta del período más reciente tal como aparece "
        "(por ejemplo: 1Q26). Sin explicaciones ni texto adicional."
    )
    try:
        raw = _content(model.invoke(prompt))
        m = _QUARTER_RE.search(raw)
        detected = f"{m.group(1)}Q{int(m.group(2)) % 100:02d}" if m else None
        if detected:
            log.info("%s: período más reciente (verificado): %s", att["filename"], detected)
            return detected
        log.warning("%s: respuesta de período no reconocida (%r); uso prior %s",
                    att["filename"], raw[:40], prior)
    except Exception:  # noqa: BLE001
        log.warning("%s: verificación de período falló; uso prior %s", att["filename"], prior)
    return prior


def _excel_period_hint(period: str | None) -> str:
    """Pista (línea de prompt) con el período más reciente del Excel, o ''."""
    if not period:
        return ""
    return (
        f"- IMPORTANTE: el período más reciente del archivo es {period}. Localiza su "
        f"columna (sin asumir si está al inicio o al final) y céntrate en {period}, "
        "comparándolo con el período inmediatamente anterior; no te quedes en "
        "trimestres más antiguos aunque aparezcan en más hojas.\n"
    )


def _content(response) -> str:
    """Normaliza la respuesta del chat model a texto plano."""
    content = getattr(response, "content", response)
    if isinstance(content, list):
        # Algunos proveedores devuelven bloques [{'type':'text','text':...}].
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return "".join(parts).strip()
    return str(content).strip()


# --- AGENTE (a): resumen por archivo --------------------------------------

def summarize_attachment(att: Attachment, settings: Settings) -> str:
    if settings.stub_mode:
        log.info("[STUB] Resumen falso para %s", att["filename"])
        return f"RESUMEN DE PRUEBA – {att['filename']}"

    # --- Fase 3: llamada real al modelo (dormida hasta STUB_MODE=false) ---
    model = _get_chat_model(settings)
    budget = settings.max_content_chars

    # Para Excel: verificación ligera del período más reciente (1 call barato).
    period = _detect_latest_period(att, model) if att["role"] == "excel" else None

    # Excel demasiado grande para el contexto -> map-reduce por bloques de hojas.
    if att["role"] == "excel" and len(att["text"]) > budget:
        return _summarize_excel_mapreduce(att, settings, model, period)

    content = _truncate(att["text"], budget, att["filename"])
    prompt = _build_summary_prompt(att, content, period)
    log.info("Resumiendo %s con %s:%s", att["filename"], settings.model_provider, settings.model_name)
    return _content(model.invoke(prompt))


def _build_summary_prompt(att: Attachment, content: str, period: str | None = None) -> str:
    """Formatea la plantilla del rol. Para Excel añade la pista del período más
    reciente (ya verificado en summarize_attachment)."""
    template = SUMMARY_PROMPTS.get(att["role"], DEFAULT_SUMMARY_PROMPT)
    if att["role"] == "excel":
        return template.format(
            filename=att["filename"],
            content=content,
            period_hint=_excel_period_hint(period),
        )
    return template.format(filename=att["filename"], content=content)


def _truncate(text: str, budget: int, filename: str) -> str:
    """Recorta a `budget` chars como salvaguarda, avisando en el log."""
    if len(text) <= budget:
        return text
    log.warning(
        "%s: texto de %d chars recortado a %d (MAX_CONTENT_CHARS).",
        filename, len(text), budget,
    )
    return text[:budget] + "\n\n[...TEXTO RECORTADO...]"


def _pack_sheets(sheets: list[str], budget: int) -> list[str]:
    """Empaqueta hojas (texto) en bloques de hasta `budget` chars, para minimizar
    el número de llamadas al modelo. Una hoja sola mayor que el budget queda en
    su propio bloque (se truncará al resumirla)."""
    chunks: list[str] = []
    current = ""
    for sheet in sheets:
        if current and len(current) + len(sheet) + 2 > budget:
            chunks.append(current)
            current = sheet
        else:
            current = f"{current}\n\n{sheet}" if current else sheet
    if current:
        chunks.append(current)
    return chunks


def _summarize_excel_mapreduce(
    att: Attachment, settings: Settings, model, period: str | None = None
) -> str:
    """Resume un Excel grande: trocea por hojas, empaqueta en bloques que quepan
    en contexto, resume cada bloque (map) y combina los parciales (reduce)."""
    from .extract import SHEET_MARKER

    budget = settings.max_content_chars
    # Trocear por marcador de hoja conservando el encabezado de cada una.
    raw_sheets = att["text"].split("\n" + SHEET_MARKER)
    sheets = [raw_sheets[0]] + [SHEET_MARKER + s for s in raw_sheets[1:]]
    sheets = [s for s in sheets if s.strip()]

    chunks = _pack_sheets(sheets, budget)
    log.info(
        "%s: Excel grande -> %d hoja(s) en %d bloque(s) (map-reduce).",
        att["filename"], len(sheets), len(chunks),
    )

    template = SUMMARY_PROMPTS["excel"]
    period_hint = _excel_period_hint(period)
    partials: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        content = _truncate(chunk, budget, f"{att['filename']} [bloque {i}]")
        log.info("Resumiendo %s (bloque %d/%d)", att["filename"], i, len(chunks))
        prompt = template.format(
            filename=att["filename"], content=content, period_hint=period_hint
        )
        partials.append(_content(model.invoke(prompt)))

    # Un solo bloque -> no hace falta reduce.
    if len(partials) == 1:
        return partials[0]

    log.info("%s: combinando %d resúmenes parciales (reduce).", att["filename"], len(partials))
    reduce_prompt = EXCEL_REDUCE_PROMPT.format(
        filename=att["filename"], partials="\n\n---\n\n".join(partials)
    )
    return _content(model.invoke(reduce_prompt))


# --- AGENTE (b): redacción del correo -------------------------------------

def draft_email(attachments: list[Attachment], subject: str, settings: Settings) -> str:
    if settings.stub_mode:
        log.info("[STUB] Redacción falsa del correo")
        lines = [
            "*** CORREO DE PRUEBA (STUB) ***",
            f"Asunto original: {subject}",
            "",
            "A continuación los resúmenes (de prueba) por archivo:",
            "",
        ]
        for a in attachments:
            lines.append(f"### {a['filename']} ({a['kind']})")
            lines.append(a["summary"])
            lines.append("")
        return "\n".join(lines)

    # --- Fase 3: llamada real al modelo (dormida hasta STUB_MODE=false) ---
    summaries = "\n\n".join(
        f"### {a['filename']} ({a['kind']})\n{a['summary']}" for a in attachments
    )
    prompt = EMAIL_PROMPT.format(subject=subject, summaries=summaries)
    model = _get_chat_model(settings)
    log.info("Redactando correo con %s:%s", settings.model_provider, settings.model_name)
    return _content(model.invoke(prompt))