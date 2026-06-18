"""Plantillas de prompts — editables en un solo lugar.

En Fase 1 NO se usan (los nodos de IA están stubeados). En Fase 3, los nodos
de modelo (`agents.py`) las formatean y se las pasan al chat model resuelto vía
`init_chat_model`. Mantenerlas agnósticas del proveedor: son solo texto.

Placeholders disponibles:
  - SUMMARY_PROMPTS[...]: {filename}, {content}
  - EMAIL_PROMPT:        {subject}, {summaries}
"""

from __future__ import annotations

# --- Una plantilla de resumen por ROL de documento ------------------------
# Las claves son el `role` del adjunto (ver src/classify.py), NO la extensión:
# la presentación puede llegar como PDF y aun así usar la plantilla de presentación.

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
    "presentation": (
        "Eres analista. A partir del texto de la presentación siguiente "
        "(archivo: {filename}) —puede venir como PDF o PPTX; si incluye NOTAS del "
        "presentador, suelen traer el guion real— redacta un resumen en español con:\n"
        "- Mensajes clave por sección/slide.\n"
        "- Conclusiones o llamadas a la acción.\n"
        "Prioriza las notas del presentador cuando aporten contexto. Usa viñetas y "
        "sé conciso.\n\n"
        "=== CONTENIDO ===\n{content}"
    ),
    "report": (
        "Eres analista. A partir del informe siguiente (archivo: {filename}), "
        "redacta un resumen en español que cubra:\n"
        "- Tesis principal del informe.\n"
        "- Riesgos señalados.\n"
        "- Cambios de rating, recomendación o perspectiva (si los hay).\n"
        "Usa viñetas y sé conciso. No inventes información ausente.\n\n"
        "=== CONTENIDO ===\n{content}"
    ),
}

# Plantilla de respaldo si apareciera un rol sin plantilla propia.
DEFAULT_SUMMARY_PROMPT = SUMMARY_PROMPTS["report"]

# Paso "reduce" del resumen de Excel grande: combina los resúmenes parciales
# (uno por bloque de hojas) en un único resumen ejecutivo coherente.
EXCEL_REDUCE_PROMPT: str = (
    "Eres analista financiero. A continuación tienes varios resúmenes PARCIALES "
    "de distintas hojas del mismo libro de Excel (archivo: {filename}), generados "
    "por separado porque el archivo era demasiado grande. Combínalos en UN solo "
    "resumen ejecutivo en español, sin repetir, centrado en:\n"
    "- Cifras clave (totales, métricas principales).\n"
    "- Variaciones relevantes (vs. periodo anterior, % cambio).\n"
    "- Cualquier anomalía o dato fuera de lo esperado.\n"
    "Usa viñetas y sé conciso.\n\n"
    "=== RESÚMENES PARCIALES ===\n{partials}"
)

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
