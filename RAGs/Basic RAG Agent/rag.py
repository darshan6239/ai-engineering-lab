from langchain_chroma import Chroma
from langchain_ollama import ChatOllama, OllamaEmbeddings

from config import (
    CHAT_MODEL,
    EMBEDDING_MODEL,
    CHROMA_DB_DIR,
    TOP_K,
)

# Chat Model
llm = ChatOllama(
    model=CHAT_MODEL,
    temperature=0
)

# Embedding Model
embedding_model = OllamaEmbeddings(
    model=EMBEDDING_MODEL
)

# Load Vector Database
vectorstore = Chroma(
    persist_directory=CHROMA_DB_DIR,
    embedding_function=embedding_model,
)

retriever = vectorstore.as_retriever(
    search_kwargs={"k": TOP_K}
)


def ask_rag(question: str):
    """
    Retrieve relevant documents and generate answer.
    """

    docs = retriever.invoke(question)

    context = "\n\n".join(
        [doc.page_content for doc in docs]
    )

    prompt = f"""
You are a helpful AI assistant.
Answer ONLY using the provided context.
If the answer is not found in the context, say:
"I couldn't find that information in the documents."

Context:
{context}

Question:
{question}
"""

    response = llm.invoke(prompt)

    sources = []

    for doc in docs:
        sources.append(
            f"{doc.metadata['source']} (Page {doc.metadata['page']+1})"
        )

    return response.content, list(set(sources))