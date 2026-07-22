"""
Builds (or rebuilds) the local Chroma vector store from ./data/*.txt using
Ollama's nomic-embed-text model — fully local, no API key required.

Run this once after adding/changing your agency's knowledge base files:
    python create_index.py
"""
import sys
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from src.config import settings, check_ollama_reachable

DATA_FILE = "./data/agency.txt"

RAG_SEARCH_PROMPT_TEMPLATE = """
Using the following pieces of retrieved context, answer the question comprehensively and concisely.
Ensure your response fully addresses the question based on the given context.

**IMPORTANT:**
Just provide the answer and never mention or refer to having access to the external context or information in your answer.
If you are unable to determine the answer from the provided context, state 'I don't know.'

Question: {question}
Context: {context}
"""


def main():
    ok, msg = check_ollama_reachable()
    if not ok:
        print(f"❌ {msg}")
        sys.exit(1)

    if not Path(DATA_FILE).exists():
        print(f"❌ {DATA_FILE} not found. Put your agency's knowledge base there first.")
        sys.exit(1)

    print("Loading & chunking docs...")
    loader = TextLoader(DATA_FILE)
    docs = loader.load()

    doc_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    doc_chunks = doc_splitter.split_documents(docs)

    print(f"Creating vector embeddings with Ollama ({settings.ollama_embed_model})...")
    embeddings = OllamaEmbeddings(model=settings.ollama_embed_model, base_url=settings.ollama_base_url)

    vectorstore = Chroma.from_documents(
        doc_chunks, embeddings, persist_directory=settings.chroma_persist_dir
    )
    vectorstore_retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    print(f"Test RAG chain (using Ollama {settings.ollama_llm_model} for the sanity check)...")
    prompt = ChatPromptTemplate.from_template(RAG_SEARCH_PROMPT_TEMPLATE)
    llm = ChatOllama(model=settings.ollama_llm_model, base_url=settings.ollama_base_url, temperature=0.1)

    rag_chain = (
        {"context": vectorstore_retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    query = "What are your pricing options?"
    result = rag_chain.invoke(query)
    print(f"Question: {query}")
    print(f"Answer: {result}")
    print(f"\n✅ Vector store built at '{settings.chroma_persist_dir}' with {len(doc_chunks)} chunks.")


if __name__ == "__main__":
    main()
