# Despliegue en Google Cloud Run

Esta app expone un webhook publico para Kommo en:

```text
/webhook/kommo
```

Cloud Run debe poder arrancar con todas las variables configuradas. No subas `.env` a GitHub.

## 1. Configura el proyecto

```powershell
gcloud auth login

$PROJECT_ID="tu-project-id"
$REGION="us-central1"
$SERVICE="kommo-integration-ia15"
$SERVICE_ACCOUNT_NAME="kommo-cloud-run"
$SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"

gcloud config set project $PROJECT_ID
```

## 2. Activa APIs

```powershell
gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com artifactregistry.googleapis.com iam.googleapis.com
```

## 3. Crea una service account para Cloud Run

```powershell
gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME `
  --display-name "Kommo Cloud Run runtime"
```

Si ya existe, Google Cloud mostrara un error de recurso existente; puedes continuar.

## 4. Crea secretos

Usa valores reales, no placeholders:

```powershell
"TU_OPENAI_API_KEY" | gcloud secrets create openai-api-key --data-file=-
"TU_LLAMA_CLOUD_API_KEY" | gcloud secrets create llama-cloud-api-key --data-file=-
"TU_KOMMO_ACCESS_TOKEN" | gcloud secrets create kommo-access-token --data-file=-
"TU_DB_PASSWORD" | gcloud secrets create supabase-db-password --data-file=-
"TU_TELEGRAM_BOT_TOKEN" | gcloud secrets create telegram-bot-token --data-file=-
```

Si un secreto ya existe, actualiza su valor con:

```powershell
"NUEVO_VALOR" | gcloud secrets versions add NOMBRE_DEL_SECRETO --data-file=-
```

## 5. Permite que Cloud Run lea los secretos

```powershell
gcloud secrets add-iam-policy-binding openai-api-key --member "serviceAccount:$SERVICE_ACCOUNT_EMAIL" --role "roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding llama-cloud-api-key --member "serviceAccount:$SERVICE_ACCOUNT_EMAIL" --role "roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding kommo-access-token --member "serviceAccount:$SERVICE_ACCOUNT_EMAIL" --role "roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding supabase-db-password --member "serviceAccount:$SERVICE_ACCOUNT_EMAIL" --role "roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding telegram-bot-token --member "serviceAccount:$SERVICE_ACCOUNT_EMAIL" --role "roles/secretmanager.secretAccessor"
```

## 6. Obtén el Telegram chat ID

Abre tu bot en Telegram y envia `/start`. Luego ejecuta:

```powershell
$env:TELEGRAM_BOT_TOKEN="TU_TELEGRAM_BOT_TOKEN"
Invoke-RestMethod "https://api.telegram.org/bot$env:TELEGRAM_BOT_TOKEN/getUpdates"
```

Busca:

```text
message.chat.id
```

Ese valor va en `TELEGRAM_CHAT_ID`.

## 7. Verifica Supabase

Para Cloud Run usa el **Session pooler** de Supabase, no el host directo `db.xxxxx.supabase.co`.

En Supabase:

```text
Project Settings > Database > Connection string > Session pooler
```

Valores esperados:

```text
DB_USER=postgres.xzeenrmqlqtbjcfgjmlv
DB_HOST=aws-0-...pooler.supabase.com
DB_PORT=5432
DB_NAME=postgres
```

## 8. Despliega

Reemplaza todos los `TU_...` antes de ejecutar:

```powershell
gcloud run deploy $SERVICE `
  --source . `
  --region $REGION `
  --service-account $SERVICE_ACCOUNT_EMAIL `
  --allow-unauthenticated `
  --memory 1Gi `
  --cpu 1 `
  --timeout 300 `
  --concurrency 10 `
  --max-instances 1 `
  --set-env-vars "BOT_NAME=Andrea,LLAMA_CLOUD_INDEX_NAME=productos_de_salud_aidev15_kommo_crm,LLAMA_CLOUD_PROJECT_NAME=Default,TELEGRAM_CHAT_ID=TU_TELEGRAM_CHAT_ID,DB_USER=postgres.xzeenrmqlqtbjcfgjmlv,DB_HOST=TU_SESSION_POOLER_HOST,DB_PORT=5432,DB_NAME=postgres,KOMMO_SUBDOMAIN=TU_KOMMO_SUBDOMAIN,KOMMO_PIPELINE_ID=TU_PIPELINE_ID,KOMMO_LEAD_INTERESADO_STATUS_ID=TU_STATUS_ID,KOMMO_LEAD_CALIFICADO_STATUS_ID=TU_STATUS_ID,KOMMO_LEAD_CERRAR_VENTA_STATUS_ID=TU_STATUS_ID,KOMMO_MARCA_INTERES_FIELD_ID=TU_FIELD_ID,KOMMO_METODO_PAGO_FIELD_ID=TU_FIELD_ID,KOMMO_SWITCH_FIELD_ID=TU_FIELD_ID,KOMMO_RESPONSE_FIELD_ID=TU_FIELD_ID,KOMMO_SALESBOT_ID=TU_SALESBOT_ID" `
  --set-secrets "OPENAI_API_KEY=openai-api-key:latest,LLAMA_CLOUD_API_KEY=llama-cloud-api-key:latest,KOMMO_ACCESS_TOKEN=kommo-access-token:latest,DB_PASSWORD=supabase-db-password:latest,TELEGRAM_BOT_TOKEN=telegram-bot-token:latest"
```

Cloud Run imprimira una URL parecida a:

```text
https://kommo-integration-ia15-xxxxx-uc.a.run.app
```

## 9. Prueba el servicio

```powershell
curl https://TU_URL_DE_CLOUD_RUN/
```

Debe responder:

```json
{"status":"ok","message":"Kommo AI Chatbot activo"}
```

## 10. Configura Kommo

En Kommo, configura el webhook hacia:

```text
https://TU_URL_DE_CLOUD_RUN/webhook/kommo
```

## 11. Ver logs

```powershell
gcloud run services logs read $SERVICE --region $REGION --limit 100
```

## 12. Problemas comunes

Si falla con `failed to resolve host db.xxxxx.supabase.co`, estas usando el direct connection. Cambia a Session pooler.

Si falla con variables faltantes, revisa el comando `--set-env-vars` y `--set-secrets`.

Si falla con LlamaCloud pipeline not found, revisa `LLAMA_CLOUD_INDEX_NAME` y `LLAMA_CLOUD_PROJECT_NAME`.

Si Telegram no envia mensajes, confirma que enviaste `/start` al bot y que `TELEGRAM_CHAT_ID` es correcto.
