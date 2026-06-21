"""
Herramienta de Retrieval: conecta con el índice en LlamaCloud
y devuelve un QueryEngineTool listo para usar con un FunctionAgent.
"""

import os
from llama_cloud.lib.index import LlamaCloudIndex
from llama_index.core.tools import QueryEngineTool


def get_index(
    index_name: str = "productos_de_salud_aidev15_kommo_crm",
    project_name: str = "Default",
):
    """Carga y devuelve el índice desde LlamaCloud."""
    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not api_key:
        raise ValueError("LLAMA_CLOUD_API_KEY no está configurada en .env")

    return LlamaCloudIndex(
        name=index_name,
        project_name=project_name,
        api_key=api_key,
    )


def get_retrieval_tool(index, llm):
    """Convierte el índice en un QueryEngineTool para el agente."""
    query_engine = index.as_query_engine(llm=llm, similarity_top_k=5)
    return QueryEngineTool.from_defaults(
        query_engine=query_engine,
        name="knowledge_base",
        description="Consulta los documentos indexados sobre productos de salud. Úsala para responder preguntas sobre su contenido.",
    )
