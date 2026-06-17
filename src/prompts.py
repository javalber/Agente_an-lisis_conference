"""Plantillas de prompts — editables en un solo lugar.

En Fase 1 NO se usan (los nodos de IA están stubeados). En Fase 3, los nodos
de modelo (`agents.py`) las formatean y se las pasan al chat model resuelto vía
`init_chat_model`. Mantenerlas agnósticas del proveedor: son solo texto.

Placeholders disponibles:
  - SUMMARY_PROMPTS[...]: {filename}, {content}
  - EMAIL_PROMPT:        {subject}, {summaries}
"""

from __future__ import annotations

# --- Una plantilla de resumen por tipo de archivo -------------------------

SUMMARY_PROMPTS: dict[str, str] = {
    "excel": (
        "Eres analista financiero. A partir del contenido de la hoja de cálculo "
        "siguiente (archivo: {filename}), redacta un resumen ejecutivo en español "
        "centrado en:\n"
        "- Cifras clave (totales, métricas principales).\n"
        "- Variaciones relevantes (vs. periodo anterior, vs. presupuesto, % cambio).\n"
        "- Cualquier anomalía o dato fuera de lo esperado.\n"
        "Sé conciso y usa viñetas. No inventes cifras que no estén en los datos.\n\n"
        "=== CONTENIDO ===\n{content}"
    ),
    "pptx": (
        "Eres analista. A partir del texto de la presentación siguiente "
        "(archivo: {filename}), que incluye el texto de cada slide y las NOTAS del "
        "presentador (el guion real), redacta un resumen en español con:\n"
        "- Mensajes clave por sección/slide.\n"
        "- Conclusiones o llamadas a la acción.\n"
        "Prioriza lo que aparezca en las notas del presentador cuando aporte "
        "contexto. Usa viñetas y sé conciso.\n\n"
        "=== CONTENIDO ===\n{content}"
    ),
    "pdf": (
        "Eres analista. A partir del informe siguiente (archivo: {filename}), "
        "redacta un resumen en español que cubra:\n"
        "- Tesis principal del informe.\n"
        "- Riesgos señalados.\n"
        "- Cambios de rating, recomendación o perspectiva (si los hay).\n"
        "Usa viñetas y sé conciso. No inventes información ausente.\n\n"
        "=== CONTENIDO ===\n{content}"
    ),
}

# --- Plantilla para redactar el correo final ------------------------------

EMAIL_PROMPT: str = (
    "Eres asistente que redacta un correo profesional en español para distribuir "
    "los resúmenes previos a una conference call.\n"
    "Asunto original del correo recibido: {subject}\n\n"
    "Redacta un correo claro y profesional que:\n"
    "- Tenga un saludo breve.\n"
    "- Presente los tres resúmenes a continuación, cada uno bajo un encabezado con "
    "el nombre del archivo.\n"
    "- Cierre con una despedida breve.\n"
    "Devuelve SOLO el cuerpo del correo (texto plano), sin asunto.\n\n"
    "=== RESÚMENES POR ARCHIVO ===\n{summaries}"
)
