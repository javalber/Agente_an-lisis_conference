# Contexto del proyecto — handoff entre sesiones

> Documento de traspaso para retomar el trabajo. Resume **qué se hizo**, **qué
> decisiones se tomaron** y **qué falta**. No sustituye al [README.md](README.md)
> (que es la doc de uso); esto es la "memoria de la obra".
>
> Última actualización: **2026-06-18** · Estado: **Fases 1 y 2 COMPLETAS**. Siguiente: **Fase 3**.

---

## 1. Objetivo del proyecto

Pipeline en Python que corre en **GitHub Actions por cron** (no en tiempo real).
El día antes de un *conference call* llega a Gmail un correo reenviado desde un
remitente conocido (correo profesional del banco) con **tres adjuntos** (Excel,
PPTX, PDF). El pipeline:

1. Busca en Gmail los correos de ese remitente **no procesados**.
2. Descarga los tres adjuntos.
3. Extrae el texto de cada archivo.
4. Resume cada archivo (uno a uno).
5. Redacta un correo con los tres resúmenes.
6. Lo envía, **con los adjuntos originales**, a una lista de destinatarios (SMTP).
7. Marca el correo de origen como `procesado` **solo si el envío fue OK**.

---

## 2. Arquitectura (qué es agente y qué no)

Orquestado como grafo **LangGraph**. **Solo 2 nodos invocan IA** ("agentes"); el
resto es código Python determinista.

```
START → extract → summarize → draft → send → (¿enviado?) → mark → END
        (det.)     (IA)        (IA)    (det.)     sí→        (det.: etiqueta)
                                                  no→ END (NO marca; reintenta)
```

| Nodo        | ¿IA? | Archivo                         |
|-------------|------|---------------------------------|
| `extract`   | No   | `src/extract.py`                |
| `summarize` | **Sí** | `src/agents.py`               |
| `draft`     | **Sí** | `src/agents.py`               |
| `send`      | No   | `src/sender.py`                 |
| `mark`      | No   | `src/gmail_ingest.py`           |

**Independencia del proveedor (requisito clave):** los nodos de IA NO conocen el
proveedor. El modelo se resuelve vía `init_chat_model` de LangChain con
`MODEL_PROVIDER` + `MODEL_NAME`. Cambiar de proveedor = cambiar esas env vars +
instalar el paquete de integración. No se toca la lógica.

---

## 3. Sintaxis confirmada contra docs vigentes (no asumida)

- `from langchain.chat_models import init_chat_model` (LangChain v1).
  Firma: `init_chat_model(model=..., model_provider=..., **kwargs)`; también
  acepta el string combinado `"anthropic:claude-..."`. Anthropic requiere el
  paquete `langchain-anthropic`.
- LangGraph: `from langgraph.graph import StateGraph, START, END`;
  `add_node` / `add_edge` / `add_conditional_edges` / `.compile()` / `.invoke()`.

---

## 4. Estructura del repo (Fase 1)

```
.
├── main.py                 # entrypoint para GitHub Actions / producción
├── run_local.py            # modo de prueba local (stub, envío solo a ti)
├── requirements.txt
├── .env.example
├── README.md               # doc de uso
├── CONTEXTO_PROYECTO.md    # este archivo
└── src/
    ├── config.py           # Settings desde env vars (sin hardcodear)
    ├── prompts.py          # plantillas de resumen + correo (editar aquí)
    ├── state.py            # tipos del estado del grafo (TypedDict)
    ├── gmail_ingest.py     # IMAP: buscar, descargar, etiquetar
    ├── extract.py          # extracción de texto PDF/Excel/PPTX
    ├── agents.py           # los 2 nodos de IA (STUBEADOS en Fase 1)
    ├── sender.py           # envío SMTP con adjuntos
    ├── graph.py            # construcción del grafo LangGraph
    └── pipeline.py         # orquestador (recorre correos pendientes)
```

---

## 5. Estado por fases

### Fase 1 — Plumbing determinista ✅ COMPLETA y verificada
- IMAP: búsqueda por `from:<remitente> has:attachment -label:procesado` vía
  `X-GM-RAW` (sintaxis nativa de Gmail). Descarga con `BODY.PEEK[]` (no marca
  como leído). Etiquetado `+X-GM-LABELS` (Gmail crea la etiqueta si no existe).
- Extracción: pdfplumber (texto+tablas), pandas+openpyxl (Excel→markdown por
  hoja), python-pptx (texto de slides **+ notas del presentador**).
- Envío SMTP SSL (puerto 465) con los adjuntos originales.
- Lógica `procesado`: solo se marca tras envío OK; cualquier fallo (extracción,
  IA, SMTP) deja el correo sin marcar para reintento. Fallos aislados por correo.
- Los 2 nodos de IA están **stubeados**: devuelven `RESUMEN DE PRUEBA – <archivo>`
  y NO contactan ninguna API.
- **Verificado sin red:** el grafo compila (nodos extract/summarize/draft/send/
  mark); extracción real de Excel y PPTX (con notas) probada con archivos
  generados al vuelo; stubs OK.

  Cómo probar local:
  ```bash
  pip install -r requirements.txt
  cp .env.example .env   # rellena GMAIL_USER, GMAIL_APP_PASSWORD, SENDER_EMAIL
  python run_local.py    # stub + envío solo a ti mismo
  ```
  ⚠️ Tras envío OK el correo de origen se etiqueta `procesado`; para re-probar,
  quita la etiqueta en Gmail.

### Fase 2 — Workflow de GitHub Actions ✅ COMPLETA
Archivo: `.github/workflows/conference_digest.yml`.
- **Zona horaria CONFIRMADA: GMT-5** (sin horario de verano → conversión estable).
  Horas locales 17/19/21/23 → **UTC 22, 0, 2, 4**. Cron: `0 22,0,2,4 * * *`.
- Disparadores: `schedule` (cron) + `workflow_dispatch` (ejecución manual de prueba).
- `concurrency` para no solapar ejecuciones; `timeout-minutes: 15`.
- `actions/checkout@v4`, `actions/setup-python@v5` (3.12, `cache: pip`),
  `pip install -r requirements.txt`, `python main.py`.
- Secrets como env: `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `SENDER_EMAIL`,
  `RECIPIENTS`, `ANTHROPIC_API_KEY`. Config no sensible (PROCESSED_LABEL,
  SUBJECT_PREFIX, MODEL_PROVIDER, MODEL_NAME, STUB_MODE) directa en el `env:`.
- **`STUB_MODE: "true"`** en el yml (Fase 2). En Fase 3 cambiar a `"false"`.
- README actualizado con la sección "GitHub Actions (Fase 2)" + tabla de secrets
  + cómo probar con `workflow_dispatch`.
- YAML validado con PyYAML (parsea OK).
- PENDIENTE de que el usuario: cree los secrets en GitHub y lance el
  `workflow_dispatch` para verificar en el runner real.

### Fase 3 — Conectar el modelo real (ÚLTIMA) ⏳
- La rama real ya está escrita en `src/agents.py` pero **dormida** tras
  `if settings.stub_mode`. Activar = poner `STUB_MODE=false` + setear la API key.
- Proveedor inicial: **Anthropic** (`MODEL_PROVIDER=anthropic`,
  `MODEL_NAME=claude-sonnet-4-6` por defecto, configurable). Requiere
  `ANTHROPIC_API_KEY`.
- Decisión abierta: el usuario puede preferir que la rama real NO exista hasta
  esta fase (hoy está gateada por el flag). Confirmar.

---

## 6. Secrets / variables de entorno

| Variable             | Descripción                                          | ¿Fase? |
|----------------------|------------------------------------------------------|--------|
| `GMAIL_USER`         | Dirección de Gmail.                                  | 1      |
| `GMAIL_APP_PASSWORD` | App Password de Google (IMAP + SMTP, requiere 2FA).  | 1      |
| `SENDER_EMAIL`       | Remitente conocido a buscar (correo del banco).      | 1      |
| `RECIPIENTS`         | Destinatarios separados por coma.                    | 1      |
| `PROCESSED_LABEL`    | Etiqueta de procesado (default `procesado`).         | 1      |
| `SUBJECT_PREFIX`     | Prefijo del asunto de salida.                        | 1      |
| `STUB_MODE`          | `true` en Fase 1/2; `false` en Fase 3.               | 1      |
| `MODEL_PROVIDER`     | Proveedor (`anthropic`).                              | 3      |
| `MODEL_NAME`         | Modelo (`claude-sonnet-4-6`).                         | 3      |
| `ANTHROPIC_API_KEY`  | API key (solo con `STUB_MODE=false`).                | 3      |

---

## 7. Decisiones tomadas (y abiertas)

- **Conexión IMAP/SMTP por operación** (abrir/cerrar por llamada): volumen bajo
  y runner efímero → más simple y robusto.
- **Rama de modelo real gateada por `STUB_MODE`** en `src/agents.py` (Fase 3 ≈
  flip de flag). *Abierto:* el usuario podría querer borrarla hasta la Fase 3.
- **`MODEL_NAME` por defecto `claude-sonnet-4-6`** (configurable).
- **Cron a las 17/19/21/23** locales en **GMT-5** (confirmado 2026-06-18) →
  `0 22,0,2,4 * * *` en UTC. GMT-5 no tiene horario de verano, conversión estable.
- Si un correo no trae los 3 tipos esperados, se registra warning pero se
  procesa con lo que haya (no se bloquea).

---

## 8. Para retomar (Fase 3) — checklist

Antes de Fase 3, el usuario debería validar la Fase 2 en el runner real:
- [ ] Crear los secrets en GitHub (GMAIL_USER, GMAIL_APP_PASSWORD, SENDER_EMAIL,
      RECIPIENTS).
- [ ] Lanzar `workflow_dispatch` y confirmar que llega el correo stub + adjuntos.

Fase 3 (modelo real):
1. Crear el secret `ANTHROPIC_API_KEY` en GitHub.
2. Cambiar `STUB_MODE` a `"false"` en el `env:` del workflow (y en `.env` local).
3. Revisar/afinar las plantillas de `src/prompts.py` con datos reales.
4. La rama real de `src/agents.py` ya invoca el modelo vía `init_chat_model`;
   no debería requerir cambios de código. Probar con `run_local.py` (sin
   `--real-recipients`) antes de fiarse del cron.
5. Decisión abierta: ¿mantener la rama real gateada por el flag o limpiarla?
