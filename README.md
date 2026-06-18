# Pipeline de resumen de conference call

Pipeline automatizado que, el día antes de un *conference call*, toma un correo
reenviado desde un remitente conocido (con tres adjuntos: Excel, PPTX y PDF),
resume cada archivo, redacta un correo con los tres resúmenes y lo reenvía —con
los adjuntos originales— a una lista de destinatarios. Pensado para correr en
**GitHub Actions por cron** (no en tiempo real).

El estado vive en **Gmail** (una etiqueta `procesado`), no en disco, porque el
runner de GitHub es efímero.

> **Estado actual: FASE 1 (plumbing determinista).**
> Los dos nodos de IA están *stubeados*: devuelven `RESUMEN DE PRUEBA – <archivo>`
> y **no contactan ninguna API**. El modelo real se conecta en la Fase 3.

---

## Arquitectura

El flujo se orquesta como un grafo **LangGraph**. Solo **dos** nodos invocan un
modelo de IA (los "agentes"); el resto es código Python determinista.

```
START → extract → summarize → draft → send → (¿enviado?) → mark → END
                  └ AGENTE IA  └ AGENTE IA         └ sí        └ etiqueta 'procesado'
        └ determinista                    └ determinista
                                          └ no → END (NO se marca; se reintenta)
```

| Nodo        | ¿IA? | Qué hace                                                   |
|-------------|------|------------------------------------------------------------|
| `extract`   | No   | Extrae texto plano (PDF/Excel/PPTX).                       |
| `summarize` | **Sí** | Resume cada archivo (una plantilla por tipo).            |
| `draft`     | **Sí** | Redacta el cuerpo del correo con los tres resúmenes.     |
| `send`      | No   | Envía por SMTP con los adjuntos originales.               |
| `mark`      | No   | Aplica la etiqueta `procesado` (solo si el envío fue OK). |

### Estructura del repo

```
.
├── main.py                 # entrypoint para GitHub Actions / producción
├── run_local.py            # modo de prueba local (stub, envío solo a ti)
├── requirements.txt
├── .env.example
└── src/
    ├── config.py           # configuración desde env vars (sin hardcodear)
    ├── prompts.py          # plantillas de resumen + correo (editar aquí)
    ├── state.py            # tipos del estado del grafo
    ├── gmail_ingest.py     # IMAP: buscar, descargar, etiquetar
    ├── extract.py          # extracción de texto PDF/Excel/PPTX
    ├── agents.py           # los 2 nodos de IA (stubeados en Fase 1)
    ├── sender.py           # envío SMTP con adjuntos
    ├── graph.py            # construcción del grafo LangGraph
    └── pipeline.py         # orquestador (recorre correos pendientes)
```

---

## Independencia del proveedor de modelo

Los nodos de IA **no** conocen el proveedor. El modelo se resuelve siempre vía
`init_chat_model` de LangChain a partir de variables de entorno:

```env
MODEL_PROVIDER=anthropic
MODEL_NAME=claude-sonnet-4-6
```

Para cambiar de proveedor (p. ej. el que te den en el trabajo) basta con cambiar
esas dos variables e instalar el paquete de integración correspondiente
(`langchain-anthropic`, `langchain-openai`, etc.) y su API key. **No se toca la
lógica de los nodos.**

---

## Modo de prueba local (Fase 1)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # rellena GMAIL_USER, GMAIL_APP_PASSWORD, SENDER_EMAIL...
python run_local.py
```

`run_local.py`:
- Carga `.env`.
- Fuerza `STUB_MODE=true` (no toca ningún modelo).
- Envía el correo **solo a ti mismo** (ignora `RECIPIENTS`).

Deberías recibir un correo con los resúmenes-stub y los tres adjuntos. Si quieres
probar la lista real de destinatarios: `python run_local.py --real-recipients`.

> **Nota:** mientras pruebas, el correo de origen **sí** se etiquetará como
> `procesado` tras un envío exitoso. Para volver a probarlo, quita la etiqueta
> `procesado` de ese correo en Gmail.

---

## Credenciales de Gmail (App Password)

1. Activa la verificación en dos pasos en tu cuenta de Google.
2. Crea una **App Password**: Cuenta de Google → Seguridad → Contraseñas de
   aplicaciones. Usa esos 16 caracteres como `GMAIL_APP_PASSWORD` (IMAP y SMTP).
3. Asegúrate de que IMAP esté habilitado en Gmail (Configuración → Reenvío y
   correo POP/IMAP).

### Variables de entorno / Secrets

| Variable             | Descripción                                                   |
|----------------------|---------------------------------------------------------------|
| `GMAIL_USER`         | Tu dirección de Gmail.                                        |
| `GMAIL_APP_PASSWORD` | App Password de Google (IMAP + SMTP).                        |
| `SENDER_EMAIL`       | Remitente conocido a buscar (tu correo del banco).           |
| `RECIPIENTS`         | Destinatarios separados por coma.                            |
| `PROCESSED_LABEL`    | Etiqueta de procesado (por defecto `procesado`).             |
| `SUBJECT_PREFIX`     | Prefijo del asunto de salida.                                |
| `STUB_MODE`          | `true` en Fase 1; `false` en Fase 3.                         |
| `MODEL_PROVIDER`     | Proveedor del modelo (p. ej. `anthropic`).                   |
| `MODEL_NAME`         | Nombre del modelo (p. ej. `claude-sonnet-4-6`).              |
| `ANTHROPIC_API_KEY`  | Solo en Fase 3 (`STUB_MODE=false`).                          |

---

## GitHub Actions (Fase 2)

El workflow [`.github/workflows/conference_digest.yml`](.github/workflows/conference_digest.yml)
ejecuta el pipeline por **cron**.

### Horario

El usuario trabaja en **GMT-5** (sin horario de verano) y quiere ejecuciones a las
**17:00, 19:00, 21:00 y 23:00** locales. GitHub Actions usa **UTC**, así que se
convierte sumando 5 horas:

| Local (GMT-5) | UTC   |
|---------------|-------|
| 17:00         | 22:00 |
| 19:00         | 00:00 |
| 21:00         | 02:00 |
| 23:00         | 04:00 |

```yaml
on:
  schedule:
    - cron: "0 22,0,2,4 * * *"
  workflow_dispatch:        # permite ejecución manual de prueba
```

> El cron de GitHub puede retrasarse algunos minutos bajo carga; no es tiempo
> real, así que es aceptable.

### Configurar los Secrets

En el repositorio: **Settings → Secrets and variables → Actions → New repository
secret**. Crea estos secrets:

| Secret               | Valor                                              |
|----------------------|----------------------------------------------------|
| `GMAIL_USER`         | Tu dirección de Gmail.                             |
| `GMAIL_APP_PASSWORD` | App Password de Google (IMAP + SMTP).             |
| `SENDER_EMAIL`       | Remitente conocido a buscar (correo del banco).   |
| `RECIPIENTS`         | Destinatarios separados por coma.                 |
| `ANTHROPIC_API_KEY`  | Solo necesario en Fase 3 (`STUB_MODE=false`).     |

La configuración no sensible (`PROCESSED_LABEL`, `SUBJECT_PREFIX`,
`MODEL_PROVIDER`, `MODEL_NAME`, `STUB_MODE`) va directa en el `env:` del workflow,
no como secret. **En Fase 2, `STUB_MODE` está en `"true"`** para probar en el
runner sin tocar el modelo.

### Probar el workflow

1. Configura los secrets de arriba.
2. Ve a la pestaña **Actions → Conference call digest → Run workflow**
   (`workflow_dispatch`) para lanzarlo manualmente, sin esperar al cron.
3. Revisa los logs del job y confirma que llega el correo con los resúmenes-stub
   y los tres adjuntos.

> ⚠️ Para que haya algo que procesar debe existir un correo del `SENDER_EMAIL`
> con los 3 adjuntos y **sin** la etiqueta `procesado`.

---

## Fases del proyecto

- **Fase 1:** plumbing determinista + nodos de IA stubeados. ✅
- **Fase 2 (actual):** workflow de GitHub Actions (cron 17/19/21/23 GMT-5,
  secrets, dependencias). ✅
- **Fase 3:** conectar el modelo real (poner `STUB_MODE=false` y la API key).
