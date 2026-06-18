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

from .config import Settings
from .prompts import DEFAULT_SUMMARY_PROMPT, EMAIL_PROMPT, SUMMARY_PROMPTS
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
    template = SUMMARY_PROMPTS.get(att["role"], DEFAULT_SUMMARY_PROMPT)
    content = att["text"]
    if len(content) > settings.max_content_chars:
        log.warning(
            "%s: texto de %d chars recortado a %d (MAX_CONTENT_CHARS).",
            att["filename"], len(content), settings.max_content_chars,
        )
        content = content[: settings.max_content_chars] + "\n\n[...TEXTO RECORTADO...]"
    prompt = template.format(filename=att["filename"], content=content)
    model = _get_chat_model(settings)
    log.info("Resumiendo %s con %s:%s", att["filename"], settings.model_provider, settings.model_name)
    return _content(model.invoke(prompt))


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