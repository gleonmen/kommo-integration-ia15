"""
Retrieval tool: connects to the LlamaCloud index and returns a QueryEngineTool.
"""

import os

from llama_cloud.lib.index import LlamaCloudIndex
from llama_index.core.tools import QueryEngineTool


DEFAULT_INDEX_NAME = "productos_de_salud_aidev15_kommo_crm"
DEFAULT_PROJECT_NAME = "Default"
DEFAULT_SIMILARITY_TOP_K = 5


def get_index(
    index_name: str | None = None,
    project_name: str | None = None,
):
    """Load and return the LlamaCloud index."""
    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not api_key:
        raise ValueError("LLAMA_CLOUD_API_KEY is not configured.")

    index_name = index_name or os.getenv("LLAMA_CLOUD_INDEX_NAME", DEFAULT_INDEX_NAME)
    project_name = project_name or os.getenv("LLAMA_CLOUD_PROJECT_NAME", DEFAULT_PROJECT_NAME)

    try:
        return LlamaCloudIndex(
            name=index_name,
            project_name=project_name,
            api_key=api_key,
        )
    except ValueError as exc:
        if "Pipeline with name" in str(exc):
            raise ValueError(
                "LlamaCloud index/pipeline not found: "
                f"'{index_name}' in project '{project_name}'. "
                "Set LLAMA_CLOUD_INDEX_NAME / LLAMA_CLOUD_PROJECT_NAME "
                "or run `python RAG/rag.py` to create/update it."
            ) from exc
        raise


def build_query_engine(index, llm, similarity_top_k: int | None = None):
    """Build the shared LlamaCloud query engine."""
    top_k = similarity_top_k or int(
        os.getenv("LLAMA_CLOUD_SIMILARITY_TOP_K", str(DEFAULT_SIMILARITY_TOP_K))
    )
    return index.as_query_engine(llm=llm, similarity_top_k=top_k)


def get_retrieval_tool(index, llm, query_engine=None):
    """Convert the index into a QueryEngineTool for the agent."""
    query_engine = query_engine or build_query_engine(index, llm)
    return QueryEngineTool.from_defaults(
        query_engine=query_engine,
        name="knowledge_base",
        description=(
            "Consulta los documentos indexados sobre productos de salud. "
            "Usala para responder preguntas sobre su contenido."
        ),
    )
