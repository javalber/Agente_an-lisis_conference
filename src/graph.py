r"""Definición del grafo LangGraph que orquesta el flujo de un correo.

Nodos:
  extract   (determinista) -> texto plano de cada adjunto.
  summarize (AGENTE / IA)  -> resumen por archivo.
  draft     (AGENTE / IA)  -> cuerpo del correo.
  send      (determinista) -> envío SMTP con adjuntos originales.
  mark      (determinista) -> etiqueta 'procesado' (SOLO si send fue OK).

Flujo:
  START -> extract -> summarize -> draft -> send --(sent?)--> mark -> END
                                                  \--(no)--> END   (no se marca)

Las dependencias (settings, gmail_client) se inyectan por closure para mantener
los nodos testeables y sin estado global.
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from .agents import draft_email, summarize_attachment
from .config import Settings
from .extract import extract_text
from .gmail_ingest import GmailClient
from .sender import send_email
from .state import PipelineState

log = logging.getLogger(__name__)


def _forward_set(state: PipelineState, settings: Settings) -> list:
    """Decide qué adjuntos se reenvían en el correo de salida, según
    FORWARD_ATTACHMENTS: 'all' | 'summarized' | 'language'."""
    mode = settings.forward_attachments
    if mode == "summarized":
        return state["to_summarize"]
    if mode == "language":
        lang = settings.summarize_language
        return [
            a for a in state["attachments"]
            if a["language"] in (lang, "neutral")
        ]
    return state["attachments"]  # 'all' (por defecto)


def build_graph(settings: Settings, gmail_client: GmailClient):
    """Construye y compila el grafo para los `settings`/`gmail_client` dados."""

    # -- Nodo determinista: extracción de texto (solo lo que se resume) --
    def extract_node(state: PipelineState) -> dict:
        updated = []
        for att in state["to_summarize"]:
            text = extract_text(att["path"], att["kind"])
            updated.append({**att, "text": text})
        return {"to_summarize": updated}

    # -- Nodo AGENTE (IA): resumen por archivo, uno a uno --
    def summarize_node(state: PipelineState) -> dict:
        updated = []
        for att in state["to_summarize"]:
            summary = summarize_attachment(att, settings)
            updated.append({**att, "summary": summary})
        return {"to_summarize": updated}

    # -- Nodo AGENTE (IA): redacción del correo --
    def draft_node(state: PipelineState) -> dict:
        body = draft_email(state["to_summarize"], state["subject"], settings)
        return {"email_body": body}

    # -- Nodo determinista: envío SMTP --
    def send_node(state: PipelineState) -> dict:
        subject = f"{settings.subject_prefix} {state['subject']}".strip()
        forward = _forward_set(state, settings)
        try:
            send_email(
                settings,
                subject=subject,
                body=state["email_body"],
                attachment_paths=[a["path"] for a in forward],
            )
            return {"sent": True, "error": None}
        except Exception as exc:  # noqa: BLE001 - se reporta y se evita marcar
            log.exception("Fallo al enviar el correo para UID %s", state["uid"])
            return {"sent": False, "error": str(exc)}

    # -- Nodo determinista: marcar procesado --
    def mark_node(state: PipelineState) -> dict:
        gmail_client.mark_processed(state["uid"])
        return {}

    # -- Enrutado tras el envío --
    def route_after_send(state: PipelineState) -> str:
        return "mark" if state.get("sent") else "end"

    builder = StateGraph(PipelineState)
    builder.add_node("extract", extract_node)
    builder.add_node("summarize", summarize_node)
    builder.add_node("draft", draft_node)
    builder.add_node("send", send_node)
    builder.add_node("mark", mark_node)

    builder.add_edge(START, "extract")
    builder.add_edge("extract", "summarize")
    builder.add_edge("summarize", "draft")
    builder.add_edge("draft", "send")
    builder.add_conditional_edges(
        "send",
        route_after_send,
        {"mark": "mark", "end": END},
    )
    builder.add_edge("mark", END)

    return builder.compile()
