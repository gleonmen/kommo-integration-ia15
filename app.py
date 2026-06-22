"""
Entrypoint FastAPI del chatbot Kommo.

Recibe webhooks de Kommo, ejecuta el agente con memoria persistente, guarda la
respuesta en el lead y lanza el Salesbot para enviarla al contacto.
"""

import asyncio
import os
import sys
import time
import traceback

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from llama_index.core.base.llms.types import ChatMessage, MessageRole

load_dotenv()


REQUIRED_ENV_VARS = [
    "OPENAI_API_KEY",
    "LLAMA_CLOUD_API_KEY",
    "KOMMO_SUBDOMAIN",
    "KOMMO_ACCESS_TOKEN",
    "KOMMO_PIPELINE_ID",
    "KOMMO_LEAD_INTERESADO_STATUS_ID",
    "KOMMO_LEAD_CALIFICADO_STATUS_ID",
    "KOMMO_LEAD_CERRAR_VENTA_STATUS_ID",
    "KOMMO_MARCA_INTERES_FIELD_ID",
    "KOMMO_METODO_PAGO_FIELD_ID",
    "KOMMO_SWITCH_FIELD_ID",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
]

REQUIRED_ENV_ALIASES = [
    ("KOMMO_RESPONSE_FIELD_ID", "KOMMO_RESPUESTA_FIELD_ID"),
    ("KOMMO_SALESBOT_ID", "KOMMO_SALESBOOT_ID"),
]


def _validate_env():
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    missing.extend(
        " or ".join(group)
        for group in REQUIRED_ENV_ALIASES
        if not any(os.getenv(var) for var in group)
    )

    if missing:
        print("\n" + "=" * 60, flush=True)
        print("Missing required environment variables:", flush=True)
        for var in missing:
            print(f"   - {var}", flush=True)
        print("=" * 60 + "\n", flush=True)
        sys.exit(1)

    print(f"{len(REQUIRED_ENV_VARS)} environment variables verified.", flush=True)


_validate_env()

sys.path.append(os.path.join(os.path.dirname(__file__), "Kommo Functions"))
from kommo import get_switch_status, launch_salesbot, parse_kommo_webhook, update_lead_with_response

from agent import build_agent_for_lead, init_resources, retrieve_catalog_context
from chat_history import get_memory_for_user


BOT_NAME = os.getenv("BOT_NAME", "Andrea")

processed_messages: dict[str, float] = {}
DEDUP_WINDOW_SECONDS = 300

print(f"Initializing agent {BOT_NAME}...", flush=True)
chat_store, token_limit = init_resources(bot_name=BOT_NAME)
print("LLM, LlamaCloud index and Postgres memory are ready.", flush=True)

app = FastAPI(title="Kommo AI Chatbot")


def _message_key(lead_id: str, text: str) -> str:
    return f"{lead_id}:{text}"


def is_duplicate(lead_id: str, text: str) -> bool:
    now = time.time()

    expired = [k for k, v in processed_messages.items() if now - v > DEDUP_WINDOW_SECONDS]
    for k in expired:
        del processed_messages[k]

    key = _message_key(lead_id, text)
    if key in processed_messages:
        return True

    processed_messages[key] = now
    return False


async def process_message(message_text: str, lead_id: str) -> dict:
    started_at = time.perf_counter()

    try:
        print(f"AI processing started | lead_id={lead_id}", flush=True)

        memory = get_memory_for_user(chat_store, lead_id, token_limit)
        agent = build_agent_for_lead(int(lead_id))
        print(f"AI resources ready | lead_id={lead_id}", flush=True)

        chat_history = memory.get(input=message_text)
        print(
            f"Chat history loaded | lead_id={lead_id} | messages={len(chat_history)}",
            flush=True,
        )

        retrieval_timeout = int(os.getenv("RETRIEVAL_TIMEOUT_SECONDS", "60"))
        try:
            catalog_context = await asyncio.wait_for(
                asyncio.to_thread(retrieve_catalog_context, message_text),
                timeout=retrieval_timeout,
            )
        except asyncio.TimeoutError:
            print(
                f"Catalog retrieval timeout | lead_id={lead_id} | timeout_seconds={retrieval_timeout}",
                flush=True,
            )
            return {"ok": False, "error": "retrieval_timeout"}

        catalog_text = catalog_context["text"]
        source_count = catalog_context["source_count"]
        print(
            f"Catalog context loaded | lead_id={lead_id} | sources={source_count} | chars={len(catalog_text)}",
            flush=True,
        )

        agent_message = (
            "Mensaje original del cliente:\n"
            f"{message_text}\n\n"
            "Informacion recuperada del catalogo oficial:\n"
            f"{catalog_text}\n\n"
            "Instrucciones para esta respuesta:\n"
            "- Responde al cliente usando la informacion recuperada del catalogo oficial.\n"
            "- No menciones herramientas, indices, bases de datos ni contexto interno.\n"
            "- Si la informacion recuperada no contiene el dato solicitado, dilo claramente.\n"
            "- Mantiene tambien las acciones de CRM que correspondan segun la intencion del cliente."
        )

        agent_timeout = int(os.getenv("AGENT_TIMEOUT_SECONDS", "180"))
        response = await asyncio.wait_for(
            agent.run(agent_message, chat_history=chat_history),
            timeout=agent_timeout,
        )
        response_text = str(response).strip()
        print(f"AI response ready | lead_id={lead_id} | chars={len(response_text)}", flush=True)

        memory.put(ChatMessage(role=MessageRole.USER, content=message_text))
        memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=response_text))
        print(f"Conversation memory saved | lead_id={lead_id}", flush=True)

        response_saved = update_lead_with_response(lead_id, response_text)
        print(f"Lead update finished | lead_id={lead_id} | ok={response_saved}", flush=True)

        salesbot_launched = launch_salesbot(lead_id)
        print(f"Salesbot launch finished | lead_id={lead_id} | ok={salesbot_launched}", flush=True)

        if not response_saved or not salesbot_launched:
            return {
                "ok": False,
                "error": "delivery_failed",
                "response_saved": response_saved,
                "salesbot_launched": salesbot_launched,
            }

        return {
            "ok": True,
            "response_saved": response_saved,
            "salesbot_launched": salesbot_launched,
        }

    except asyncio.TimeoutError:
        timeout_seconds = os.getenv("AGENT_TIMEOUT_SECONDS", "180")
        print(
            f"AI processing timeout | lead_id={lead_id} | timeout_seconds={timeout_seconds}",
            flush=True,
        )
        return {"ok": False, "error": "agent_timeout"}

    except Exception as exc:
        traceback.print_exc()
        print(f"Error processing message | lead_id={lead_id} | error={exc}", flush=True)
        return {"ok": False, "error": str(exc)}

    finally:
        elapsed = time.perf_counter() - started_at
        print(f"AI processing finished | lead_id={lead_id} | seconds={elapsed:.2f}", flush=True)


@app.get("/")
async def root():
    return {"status": "ok", "message": "Kommo AI Chatbot activo"}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/webhook/kommo")
async def kommo_webhook(request: Request):
    body = await request.body()
    data = parse_kommo_webhook(body)

    message_text = data.get("text", "")
    lead_id = data.get("lead_id")
    message_type = data.get("type", "")
    created_by = data.get("created_by")

    if message_type and message_type == "outgoing":
        return {"status": "ignored", "reason": "outgoing message"}

    if created_by and str(created_by) != "0":
        return {"status": "ignored", "reason": "system message"}

    if not message_text or not lead_id:
        return {"status": "ignored", "reason": "missing data"}

    if len(message_text.strip()) < 1:
        return {"status": "ignored", "reason": "empty message"}

    if is_duplicate(lead_id, message_text):
        print(f"Duplicate webhook ignored | lead_id={lead_id}", flush=True)
        return {"status": "ignored", "reason": "duplicate webhook"}

    if not get_switch_status(lead_id):
        print(f"AI switch off | lead_id={lead_id}", flush=True)
        return {"status": "ignored", "reason": "AI switch off"}

    print("Kommo webhook received.", flush=True)
    print(f"Message received | lead_id={lead_id} | chars={len(message_text)}", flush=True)

    result = await process_message(message_text, lead_id)
    if not result.get("ok"):
        processed_messages.pop(_message_key(lead_id, message_text), None)
        return {
            "status": "error",
            "reason": result.get("error", "processing_failed"),
            "response_saved": result.get("response_saved"),
            "salesbot_launched": result.get("salesbot_launched"),
        }

    return {
        "status": "ok",
        "message": "processed",
        "response_saved": result.get("response_saved"),
        "salesbot_launched": result.get("salesbot_launched"),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
