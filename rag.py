"""
git clone https://huggingface.co/{REPO_NAME}-dbfiles

REPO_NAME = REPO_NAME.split("/")[1]
mv {REPO_NAME}/* ./
rm -rf {REPO_NAME}
"""


import os

import logging
import sys

from langchain_chroma import Chroma
from langchain.storage import LocalFileStore
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LANGCHAIN_API_KEY= os.getenv("LANGCHAIN_API_KEY")
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["LANGCHAIN_API_KEY"] = LANGCHAIN_API_KEY
os.environ["LANGCHAIN_TRACING_V2"] = "true" # Enable LangSmith tracing


# --- Paths and Constants ---
store_path = "docstore/"
vectorstore_path = "chroma_db/"
db_path = "processed_files.db"
id_key = "doc_id"

os.makedirs(store_path, exist_ok=True)
os.makedirs(vectorstore_path, exist_ok=True)


# --- Retriever ---
import chromadb
client = chromadb.PersistentClient(path=vectorstore_path)

vectorstore = Chroma(
    client=client,
    collection_name="multimodal-rag-colab", # not multimodal anymore, since we removed images (fk images, all ma hoemies hate images).
    embedding_function=OpenAIEmbeddings(
        model="text-embedding-3-small",
        disallowed_special=(),
    ),
    persist_directory=vectorstore_path
)
fs = LocalFileStore(store_path)
retriever = MultiVectorRetriever(vectorstore=vectorstore, docstore=fs, id_key=id_key, search_type="similarity", retrieval_type="vectorstore")


def parse_retrieved_docs(docs):
    """
    Parses retrieved Document objects, loading original content from the docstore
    and categorizing them by type (text, table).
    """
    parsed_texts = []
    parsed_tables = []

    # 'docs' is a list of Document objects returned by the retriever.
    # Each Document has page_content (the embedded summary/chunk) and metadata.
    # all ma hoemies use the 'doc_id' from metadata to fetch the original content from docstore.
    doc_ids_to_fetch = [doc.metadata[id_key] for doc in docs if id_key in doc.metadata]

    if not doc_ids_to_fetch:
        logger.warning("No document IDs found in retrieved documents to fetch from docstore.")
        return {"texts": [], "tables": []}

    try:
        # mget returns a list of contents corresponding to the input list of IDs
        contents_bytes = retriever.docstore.mget(doc_ids_to_fetch)

        for i, content_bytes in enumerate(contents_bytes):
            if content_bytes is None:
                logger.warning(f"Content for doc_id {doc_ids_to_fetch[i]} not found in docstore. Skipping.")
                continue

            try:
                content = content_bytes.decode('utf-8')
                doc_type = docs[i].metadata.get("doc_type", "unknown")
                source_file = docs[i].metadata.get("source_file", "N/A")

                if doc_type == "table":
                    parsed_tables.append(f"--- Table from {os.path.basename(source_file)} ---\n{content}\n--- End Table ---")
                elif doc_type == "text":
                    parsed_texts.append(f"--- Text from {os.path.basename(source_file)} ---\n{content}\n--- End Text ---")
                else:
                    logger.warning(f"Document with unknown doc_type '{doc_type}' from {source_file}. Appending as text.")
                    parsed_texts.append(f"--- Unknown Document Type from {os.path.basename(source_file)} ---\n{content}\n--- End Unknown Type ---")

            except UnicodeDecodeError:
                logger.error(f"Could not decode content for doc_id {doc_ids_to_fetch[i]} from {docs[i].metadata.get('source_file', 'N/A')}. Skipping.")
    except Exception as e:
        logger.error(f"Error processing doc_id {doc_ids_to_fetch[i]} from {docs[i].metadata.get('source_file', 'N/A')}: {e}", exc_info=True)

    return {"texts": parsed_texts, "tables": parsed_tables}


def build_prompt(inputs):
    """
    Builds a multi-modal prompt from structured context (texts, tables) and a question.
    Formats the context clearly for the LLM.
    """
    context_parts = []

    if inputs["context"].get("texts"):
        context_parts.append("--- Retrieved Text Content ---")
        context_parts.extend(inputs["context"]["texts"])

    if inputs["context"].get("tables"):
        if context_parts:
            context_parts.append("\n")
        context_parts.append("--- Retrieved Table Content (as HTML) ---")
        context_parts.extend(inputs["context"]["tables"])


    context_text = "\n\n".join(context_parts)

    if not context_text.strip():
        prompt_template = (
            f"No relevant context was found for the question: '{inputs['question']}'. "
            "Please state that you cannot answer based on the provided information."
        )
    else:
        prompt_template = (
            f"Answer the question based ONLY on the provided context. "
            f"The context may include plain text and tables represented as HTML. "
            f"Summarize tables concisely if they are relevant to the question. "
            f"If the answer is not in the context, state that you cannot answer.\n\n"
            f"Context:\n{context_text}\n\n"
            f"Question: {inputs['question']}"
        )

    prompt_content = [{"type": "text", "text": prompt_template}]
    return [HumanMessage(content=prompt_content)]

# --- Final RAG Chain ---
final_model = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, max_tokens=1024)
rag_chain = (
    {
        "context": retriever.vectorstore.as_retriever() | RunnableLambda(parse_retrieved_docs),
        "question": RunnablePassthrough()
    }
    | RunnableLambda(build_prompt)
    | final_model
    | StrOutputParser()
)

async def query_rag(question: str):
    """
    Queries the RAG pipeline with a question and returns the response.
    """
    logger.info(f"Querying RAG with: '{question}'")
    response = rag_chain.invoke(question)
    logger.info(f"RAG response: '{response}'")
    return response

async def main():
    logger.info("\n--- RAG Pipeline Ready for Query ---")

    question = "gemini code snippet to initialize a client"
    logger.info(f"Querying with: '{question}'")

    # Invoke the chain and print the response
    response = await query_rag(question)

    print("\n--- Response ---")
    print(response)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())