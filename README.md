# Kommo Integration IA15

Integracion didactica entre Facebook Messenger, Kommo CRM, un agente IA con
LlamaIndex/LlamaCloud y Google Cloud Run.

El flujo esperado es:

```text
Facebook Messenger -> Kommo -> /webhook/kommo -> Agente IA -> Kommo -> Salesbot -> Cliente
```

La app recibe mensajes desde Kommo, consulta el catalogo de productos en
LlamaCloud, genera una respuesta con OpenAI, guarda esa respuesta en un campo
custom del lead y lanza un Salesbot para enviarla al chat del cliente.

## Componentes

- `app.py`: API FastAPI y endpoint `/webhook/kommo`.
- `agent.py`: inicializa el LLM, LlamaCloud, memoria y tools del agente.
- `tools/retrieval.py`: conexion al indice LlamaCloud.
- `Kommo Functions/kommo.py`: helpers para parsear webhooks, leer switch IA,
  actualizar leads y lanzar Salesbot.
- `chat_history/postgres_store.py`: memoria persistente por `lead_id` usando
  Supabase/Postgres.
- `tools/send_notification_by_telegram.py`: tool para enviar notificaciones por
  Telegram.
- `RAG/rag.py`: ingesta de documentos desde `Base de Conocimiento/` hacia
  LlamaCloud.
- `Dockerfile`: contenedor para Cloud Run.
- `DEPLOY_CLOUD_RUN.md`: guia paso a paso del despliegue.

## Cambios importantes realizados

1. Se agrego soporte para Google Cloud Run con `Dockerfile`,
   `.dockerignore`, `.gcloudignore` y `cloudrun.env.example`.
2. Se corrigio el error `cannot pickle 'module' object`:
   - Antes se pasaba `memory` completo a `agent.run(...)`.
   - Ahora se pasa `chat_history` y se guarda manualmente el historial con
     `ChatMessage`.
3. Se elimino el procesamiento critico en `BackgroundTasks`.
   - En Cloud Run, las tareas en background pueden quedar congeladas por CPU
     throttling despues de responder `200 OK`.
   - Ahora el webhook responde `processed` solo despues de generar respuesta,
     guardar en Kommo y lanzar el Salesbot.
4. Se forzo el uso del indice LlamaCloud antes de responder.
   - El webhook consulta el catalogo con `retrieve_catalog_context(...)`.
   - Luego inyecta ese contexto al agente para evitar respuestas genericas.
   - En logs debe verse `Catalog context loaded | sources=...`.
5. Se agregaron logs por etapa para diagnostico:
   - `AI processing started`
   - `Catalog context loaded`
   - `AI response ready`
   - `Lead update finished`
   - `Salesbot launch finished`
6. Se agrego Telegram como tool:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
7. Se agrego soporte para aliases de variables:
   - `KOMMO_RESPONSE_FIELD_ID` o `KOMMO_RESPUESTA_FIELD_ID`
   - `KOMMO_SALESBOT_ID` o `KOMMO_SALESBOOT_ID`
8. Se recomendo usar Supabase Session Pooler para Cloud Run.

## Variables de entorno

No subas `.env` a GitHub. El archivo esta ignorado por `.gitignore`.

Usa `cloudrun.env.example` como referencia:

```text
BOT_NAME=Andrea

OPENAI_API_KEY=replace-me
LLAMA_CLOUD_API_KEY=replace-me
LLAMA_CLOUD_INDEX_NAME=productos_de_salud_aidev15_kommo_crm
LLAMA_CLOUD_PROJECT_NAME=Default
LLAMA_CLOUD_SIMILARITY_TOP_K=5

KOMMO_SUBDOMAIN=replace-me
KOMMO_ACCESS_TOKEN=replace-me
KOMMO_PIPELINE_ID=replace-me
KOMMO_LEAD_INTERESADO_STATUS_ID=replace-me
KOMMO_LEAD_CALIFICADO_STATUS_ID=replace-me
KOMMO_LEAD_CERRAR_VENTA_STATUS_ID=replace-me
KOMMO_MARCA_INTERES_FIELD_ID=replace-me
KOMMO_METODO_PAGO_FIELD_ID=replace-me
KOMMO_SWITCH_FIELD_ID=replace-me
KOMMO_RESPONSE_FIELD_ID=replace-me
KOMMO_SALESBOT_ID=replace-me

TELEGRAM_BOT_TOKEN=replace-me
TELEGRAM_CHAT_ID=replace-me

DB_USER=replace-me
DB_PASSWORD=replace-me
DB_HOST=replace-with-session-pooler-host.pooler.supabase.com
DB_PORT=5432
DB_NAME=postgres

AGENT_TIMEOUT_SECONDS=180
RETRIEVAL_TIMEOUT_SECONDS=60
```

Para Cloud Run, guarda valores sensibles en Secret Manager:

- `OPENAI_API_KEY`
- `LLAMA_CLOUD_API_KEY`
- `KOMMO_ACCESS_TOKEN`
- `DB_PASSWORD`
- `TELEGRAM_BOT_TOKEN`

## LlamaCloud / RAG

Los documentos del catalogo viven en:

```text
Base de Conocimiento/
```

Para crear o actualizar el indice:

```powershell
python RAG/rag.py
```

El indice usado por defecto es:

```text
productos_de_salud_aidev15_kommo_crm
```

Para verificar localmente que LlamaCloud devuelve datos:

```powershell
python -c "from dotenv import load_dotenv; load_dotenv('.env'); from agent import init_resources, retrieve_catalog_context; init_resources('Andrea'); r=retrieve_catalog_context('quiero informacion de los productos del catalogo'); print(r['source_count']); print(r['text'][:1000])"
```

Si funciona, debes ver productos como `VitaCalm`, `CogniBoost`, `JointFlex` e
`Infusion de Energia Natural`.

## Ejecucion local

Instala dependencias:

```powershell
pip install -r requirements.txt
```

Ejecuta la API:

```powershell
python app.py
```

La app local escucha en:

```text
http://localhost:8000
```

Prueba raiz:

```powershell
curl.exe -i http://localhost:8000/
```

## Endpoint Kommo

Endpoint principal:

```text
POST /webhook/kommo
```

Kommo envia datos como `application/x-www-form-urlencoded`. Ejemplo de prueba:

```powershell
curl.exe -i --http1.1 -X POST "https://TU_URL_CLOUD_RUN/webhook/kommo" `
  -H "Content-Type: application/x-www-form-urlencoded" `
  --data-urlencode "message[add][0][text]=quiero informacion de los productos" `
  --data-urlencode "message[add][0][element_id]=TU_LEAD_ID" `
  --data-urlencode "message[add][0][type]=incoming" `
  --data-urlencode "message[add][0][created_by]=0"
```

Respuesta esperada si todo funciona:

```json
{
  "status": "ok",
  "message": "processed",
  "response_saved": true,
  "salesbot_launched": true
}
```

## Despliegue en Cloud Run

Guia completa:

```text
DEPLOY_CLOUD_RUN.md
```

Comando base:

```powershell
gcloud run deploy kommo-integration-ia15 `
  --source . `
  --region us-central1 `
  --project TU_PROJECT_ID `
  --allow-unauthenticated `
  --timeout 300 `
  --concurrency 10 `
  --memory 1Gi `
  --cpu 1 `
  --no-cpu-throttling `
  --update-env-vars "BOT_NAME=Andrea,LLAMA_CLOUD_INDEX_NAME=productos_de_salud_aidev15_kommo_crm,LLAMA_CLOUD_PROJECT_NAME=Default,LLAMA_CLOUD_SIMILARITY_TOP_K=5,AGENT_TIMEOUT_SECONDS=180,RETRIEVAL_TIMEOUT_SECONDS=60,TELEGRAM_CHAT_ID=TU_TELEGRAM_CHAT_ID,DB_USER=TU_DB_USER,DB_HOST=TU_SESSION_POOLER_HOST,DB_PORT=5432,DB_NAME=postgres,KOMMO_SUBDOMAIN=TU_KOMMO_SUBDOMAIN,KOMMO_PIPELINE_ID=TU_PIPELINE_ID,KOMMO_LEAD_INTERESADO_STATUS_ID=TU_STATUS_ID,KOMMO_LEAD_CALIFICADO_STATUS_ID=TU_STATUS_ID,KOMMO_LEAD_CERRAR_VENTA_STATUS_ID=TU_STATUS_ID,KOMMO_MARCA_INTERES_FIELD_ID=TU_FIELD_ID,KOMMO_METODO_PAGO_FIELD_ID=TU_FIELD_ID,KOMMO_SWITCH_FIELD_ID=TU_FIELD_ID,KOMMO_RESPONSE_FIELD_ID=TU_FIELD_ID,KOMMO_SALESBOT_ID=TU_SALESBOT_ID" `
  --set-secrets "OPENAI_API_KEY=openai-api-key:latest,LLAMA_CLOUD_API_KEY=llama-cloud-api-key:latest,KOMMO_ACCESS_TOKEN=kommo-access-token:latest,DB_PASSWORD=supabase-db-password:latest,TELEGRAM_BOT_TOKEN=telegram-bot-token:latest"
```

Nota: para Supabase en Cloud Run usa **Session Pooler**, no Direct Connection.

## Configuracion en Kommo

Configura el webhook de Kommo hacia:

```text
https://TU_URL_CLOUD_RUN/webhook/kommo
```

El lead debe tener el campo de switch IA activo:

```text
KOMMO_SWITCH_FIELD_ID
```

La respuesta del agente se guarda en:

```text
KOMMO_RESPONSE_FIELD_ID
```

El Salesbot configurado en:

```text
KOMMO_SALESBOT_ID
```

debe enviar al chat el contenido del campo de respuesta.

## Telegram

Para obtener `TELEGRAM_CHAT_ID`:

1. Abre el bot en Telegram.
2. Envia `/start`.
3. Llama a:

```powershell
Invoke-RestMethod "https://api.telegram.org/bot<TU_TELEGRAM_BOT_TOKEN>/getUpdates"
```

Busca:

```text
message.chat.id
```

Ese valor va en `TELEGRAM_CHAT_ID`.

## Verificacion en Cloud Run

Ver servicio activo:

```powershell
gcloud run services describe kommo-integration-ia15 `
  --region us-central1 `
  --project TU_PROJECT_ID `
  --format "value(status.latestReadyRevisionName,status.traffic[0].revisionName,status.traffic[0].percent,status.url)"
```

Ver logs recientes:

```powershell
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=kommo-integration-ia15" `
  --project TU_PROJECT_ID `
  --freshness=30m `
  --limit=100 `
  --format "value(timestamp,resource.labels.revision_name,textPayload)"
```

Logs saludables para una pregunta de productos:

```text
Kommo webhook received.
AI processing started
Chat history loaded
Catalog context loaded | sources=5
AI response ready
Conversation memory saved
Lead update finished | ok=True
Salesbot launch finished | ok=True
AI processing finished
```

## Troubleshooting

`cannot pickle 'module' object`

Este error venia de pasar `memory` completo a `agent.run(...)`. La version actual
usa `chat_history` y guarda la memoria manualmente.

`Catalog context loaded` no aparece

El flujo no esta llegando a LlamaCloud. Revisa:

- `LLAMA_CLOUD_API_KEY`
- `LLAMA_CLOUD_INDEX_NAME`
- `LLAMA_CLOUD_PROJECT_NAME`
- que `RAG/rag.py` haya subido documentos

El agente responde pero no habla de productos

Verifica en logs que aparezca:

```text
Catalog context loaded | sources=5
```

Si `sources=0`, el indice no esta devolviendo documentos relevantes.

El endpoint responde `AI switch off`

El lead no tiene activo el campo `KOMMO_SWITCH_FIELD_ID`, o Kommo no devolvio el
lead correctamente.

La respuesta se guarda en Kommo pero no llega al cliente

Cloud Run ya hizo su parte si ves:

```text
Lead update finished | ok=True
Salesbot launch finished | ok=True
```

En ese caso revisa el Salesbot en Kommo. Debe leer y enviar el campo
`KOMMO_RESPONSE_FIELD_ID`.

Error conectando a Supabase

En Cloud Run usa el host del **Session Pooler**:

```text
aws-...pooler.supabase.com
```

No uses el host directo:

```text
db.xxxxx.supabase.co
```

## Seguridad

- No subas `.env`.
- No pegues tokens en issues o commits.
- Usa Secret Manager para secretos en Cloud Run.
- Rota credenciales si fueron compartidas fuera del entorno local.
