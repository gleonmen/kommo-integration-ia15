import os
from dotenv import load_dotenv
import logging
import sys

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(message)s'
)

logging.getLogger("httpx").setLevel(logging.WARNING)

load_dotenv()

from llama_index.core import SimpleDirectoryReader, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_cloud.lib.index import LlamaCloudIndex

# Configuración de LlamaCloud
LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
LLAMA_CLOUD_INDEX_NAME = "productos_de_salud_aidev15_kommo_crm"


# ==================== PIPELINE RAG ====================
# Dividimos el pipeline en 4 pasos claros:
#   1. Document Loader        → Cargar archivos (PDF, TXT, DOCX, etc.)
#   2. Document Splitting     → Dividir en chunks manejables
#   3. Embedding Process       → Convertir texto a vectores numéricos
#   4. Vector Store            → Subir vectores a LlamaCloud
# ======================================================


# --------------- Paso 2: Document Splitting (Chunking) ----------------
# Definimos CÓMO se dividirán los documentos largos en trozos (chunks).
# El LLM tiene un límite de contexto, así que dividimos en párrafos
# significativos con superposición para no perder contexto entre chunks.

Settings.text_splitter = SentenceSplitter(
    chunk_size=512,      # Tamaño de cada chunk en tokens (512 o 1024 son buenos puntos de partida)
    chunk_overlap=50     # Superposición entre chunks consecutivos (~10-15% del chunk_size)
)

logging.info(f"Configurado el divisor de texto: chunk_size={Settings.text_splitter.chunk_size}, chunk_overlap={Settings.text_splitter.chunk_overlap}")


# --------------- Paso 3: Embedding Process ----------------------------
# Modelo que convierte los chunks de texto en vectores numéricos (embeddings).
# Es crucial usar el MISMO modelo tanto para la ingesta como para las consultas.
# "text-embedding-3-small" de OpenAI es eficiente y potente.

Settings.embed_model = OpenAIEmbedding(
    model="text-embedding-3-small",
    dimensions=1536      # Dimensiones del vector; debe coincidir con la config del vector store
)

logging.info(f"Configurado el modelo de embeddings: {Settings.embed_model.model_name}")


def ingest_data():
    """
    Ejecuta el pipeline completo de ingesta de datos:
      Paso 1 → Document Loader: Lee los archivos de 'Base de Conocimiento'
      Paso 2 → Splitting: Ya configurado globalmente en Settings.text_splitter
      Paso 3 → Embeddings: Ya configurado globalmente en Settings.embed_model
      Paso 4 → Vector Store: Sube los documentos al índice en LlamaCloud
    """

    # --------------- Paso 1: Document Loader ------------------------------
    # LlamaIndex busca en la carpeta especificada y usa el cargador adecuado
    # para cada tipo de archivo (.txt, .pdf, .docx, etc.).
    # Carga todo el contenido en memoria como objetos Document.

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    knowledge_base_path = os.path.join(project_root, "Base de Conocimiento")

    logging.info(f"Buscando documentos en la carpeta '{knowledge_base_path}'...")

    if not os.path.exists(knowledge_base_path):
        logging.error(f"❌ La carpeta '{knowledge_base_path}' no existe.")
        raise FileNotFoundError(f"No se encontró la carpeta: {knowledge_base_path}")

    documents = SimpleDirectoryReader(knowledge_base_path).load_data()

    if not documents:
        logging.warning("No se encontraron documentos para procesar. Finalizando.")
        return None

    logging.info("=" * 80)
    logging.info(f"📄 DOCUMENTOS ENCONTRADOS: {len(documents)}")
    logging.info("=" * 80)
    for i, doc in enumerate(documents, 1):
        doc_name = getattr(doc, 'metadata', {}).get('file_name', f'Documento {i}')
        logging.info(f"  {i}. {doc_name}")
    logging.info("=" * 80)

    # --------------- Paso 4: Vector Store (LlamaCloud) --------------------
    # LlamaCloud maneja automáticamente el splitting (Paso 2) y los
    # embeddings (Paso 3) en el servidor usando la configuración global.
    # Aquí subimos los documentos al índice en la nube.

    logging.info(f"\n🚀 Iniciando proceso de subida de {len(documents)} documentos a LlamaCloud...")

    if not LLAMA_CLOUD_API_KEY:
        raise ValueError("LLAMA_CLOUD_API_KEY no está configurada en las variables de entorno.")

    index = None
    index_exists = False

    try:
        logging.info(f"🔍 Buscando índice existente '{LLAMA_CLOUD_INDEX_NAME}'...")
        index = LlamaCloudIndex(
            name=LLAMA_CLOUD_INDEX_NAME,
            project_name="Default",
            api_key=LLAMA_CLOUD_API_KEY,
        )
        index_exists = True
        logging.info(f"✅ Índice '{LLAMA_CLOUD_INDEX_NAME}' encontrado.")
        logging.info(f"📤 Insertando {len(documents)} documentos en el índice existente...")

        index.insert(documents)
        logging.info(f"✅ {len(documents)} documentos insertados exitosamente.")

    except Exception as load_error:
        error_msg = str(load_error)

        if "429" in error_msg or "maximum number of indexes" in error_msg.lower():
            logging.error("❌ Has alcanzado el límite máximo de índices (5) en tu plan free.")
            logging.error("Solución: Elimina índices desde https://cloud.llamaindex.ai")
            raise ValueError(
                "Límite de índices alcanzado. Elimina índices no utilizados desde "
                "https://cloud.llamaindex.ai o actualiza tu plan."
            )

        if not index_exists:
            logging.info(f"📝 Índice no encontrado. Creando nuevo índice '{LLAMA_CLOUD_INDEX_NAME}'...")
            logging.info(f"📤 Subiendo {len(documents)} documentos a LlamaCloud...")
            logging.info("⏳ Esto puede tardar varios minutos. Por favor, espera...")

            index = LlamaCloudIndex.from_documents(
                documents=documents,
                name=LLAMA_CLOUD_INDEX_NAME,
                project_name="Default",
                api_key=LLAMA_CLOUD_API_KEY,
            )
            logging.info(f"✅ {len(documents)} documentos subidos exitosamente.")
        else:
            raise

    logging.info("\n" + "=" * 80)
    logging.info("✅ PROCESO COMPLETADO EXITOSAMENTE")
    logging.info("=" * 80)
    logging.info(f"📊 Resumen:")
    logging.info(f"   • Documentos procesados: {len(documents)}")
    logging.info(f"   • Índice: '{LLAMA_CLOUD_INDEX_NAME}'")
    logging.info(f"   • Estado: {'Actualizado' if index_exists else 'Creado'}")
    logging.info("=" * 80)

    return index


if __name__ == "__main__":
    try:
        index = ingest_data()
        if index:
            print("\n" + "=" * 80)
            print("✅ PROCESO COMPLETADO EXITOSAMENTE")
            print("=" * 80)
            print(f"Índice '{LLAMA_CLOUD_INDEX_NAME}' está listo para usar en LlamaCloud.")
            print("=" * 80 + "\n")
        else:
            print("\n⚠️  El proceso no retornó un índice. Verifica los logs arriba.\n")
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario.\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error fatal: {e}\n")
        sys.exit(1)
