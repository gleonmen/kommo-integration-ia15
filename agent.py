"""
Módulo Agente IA (FunctionAgent) para el flujo de Kommo CRM.

Configuración modular:
- LLM + parámetros de memoria: model_config/model.yaml
- System prompt:                prompt/system_prompt.yaml
- Histórico de conversación:    chat_history/  (Postgres / Supabase)
- Credenciales DB y BOT_NAME:   .env

Arquitectura tool-calling:
- `init_resources(bot_name)` se llama UNA vez al arrancar el app. Carga el LLM,
  el índice (LlamaCloud), arma el retrieval tool, renderiza el system_prompt y
  crea el chat_store (Postgres). Devuelve `(chat_store, token_limit)` para que
  el entrypoint lo use al construir la memoria por lead.

- `build_agent_for_lead(lead_id)` se llama por cada mensaje entrante. Construye
  un FunctionAgent ligero con los 6 tools enlazados a ese lead_id concreto:
    1. knowledge_base (retrieval del catálogo, compartido)
    2. move_to_Lead_Interesado
    3. move_to_Lead_Calificado
    4. move_to_Cerrar_Venta
    5. update_Marca_de_Interes
    6. update_Metodo_de_Pago
  El agente DECIDE cuándo invocar cada tool según el contexto.
"""

from pathlib import Path

import yaml
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI

from chat_history import build_chat_store
from tools.retrieval import get_index, get_retrieval_tool
from tools.move_lead_to_Lead_Interesado import get_move_to_Lead_Interesado_tool
from tools.move_lead_to_Lead_Calificado import get_move_to_Lead_Calificado_tool
from tools.move_lead_to_Cerrar_Venta import get_move_to_Cerrar_Venta_tool
from tools.update_data_Marca_de_Interes import get_update_Marca_de_Interes_tool
from tools.update_data_Metodo_de_Pago import get_update_Metodo_de_Pago_tool

# ──────────────────────────────────────────────
# 0. CARGA DE CONFIGURACIÓN MODULAR
# ──────────────────────────────────────────────

ROOT = Path(__file__).parent
LLM_CONFIG_PATH = ROOT / "model_config" / "model.yaml"
PROMPT_CONFIG_PATH = ROOT / "prompt" / "system_prompt.yaml"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _render_system_prompt(bot_name: str) -> str:
    """Carga el system_prompt.yaml y reemplaza los placeholders {variable}."""
    prompt_cfg = _load_yaml(PROMPT_CONFIG_PATH)
    return prompt_cfg["system_prompt"].replace("{bot_name}", bot_name)


# ──────────────────────────────────────────────
# 1. RECURSOS COMPARTIDOS (singletons, init una vez)
# ──────────────────────────────────────────────

_llm = None
_retrieval_tool = None
_system_prompt = None


def init_resources(bot_name: str):
    """
    Inicializa los recursos compartidos del agente (LLM, índice, retrieval tool,
    system prompt y chat_store). Llamar una sola vez al arrancar el app.

    Returns:
        tuple: (chat_store, token_limit)
        - chat_store: PostgresChatStore compartido entre leads
        - token_limit: tope de tokens del historial, leído del YAML
    """
    global _llm, _retrieval_tool, _system_prompt

    config = _load_yaml(LLM_CONFIG_PATH)
    llm_cfg = config["llm"]
    mem_cfg = config["memory"]

    _llm = OpenAI(
        model=llm_cfg["model"],
        temperature=llm_cfg.get("temperature", 0),
    )

    index = get_index()
    _retrieval_tool = get_retrieval_tool(index, _llm)

    _system_prompt = _render_system_prompt(bot_name)

    chat_store = build_chat_store(table_name=mem_cfg["table_name"])

    return chat_store, mem_cfg["token_limit"]


# ──────────────────────────────────────────────
# 2. AGENTE POR LEAD (lightweight, recreado por mensaje)
# ──────────────────────────────────────────────

def build_agent_for_lead(lead_id: int) -> FunctionAgent:
    """
    Construye un FunctionAgent con tools enlazadas al lead_id especificado.
    Se recrea por cada mensaje entrante: el LLM, el índice y el retrieval tool
    son singletons cacheados; solo el FunctionAgent y las tools de acción se
    reconstruyen (es barato).
    """
    if _llm is None:
        raise RuntimeError(
            "Recursos no inicializados. Llama a init_resources(bot_name) primero."
        )

    tools = [
        _retrieval_tool,
        get_move_to_Lead_Interesado_tool(lead_id),
        get_move_to_Lead_Calificado_tool(lead_id),
        get_move_to_Cerrar_Venta_tool(lead_id),
        get_update_Marca_de_Interes_tool(lead_id),
        get_update_Metodo_de_Pago_tool(lead_id),
    ]

    return FunctionAgent(
        tools=tools,
        llm=_llm,
        system_prompt=_system_prompt,
    )
