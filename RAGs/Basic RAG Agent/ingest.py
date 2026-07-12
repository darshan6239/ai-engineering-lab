from pathlib import Path
import shutil

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

from config import (
    DATA_PATH,
    CHROMA_DB_DIR,
    EMBEDDING_MODEL,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)


def load_documents():
    """Load all PDF documents from the data folder."""
    pdf_folder = Path(DATA_PATH)
    pdf_files = list(pdf_folder.glob("*.pdf"))

    if not pdf_files:
        raise FileNotFoundError(
            f"No PDF files found inside: {pdf_folder.resolve()}"
        )

    documents = []
    print("\nLoading PDFs...\n")

    for pdf in pdf_files:
        print(f"✓ {pdf.name}")
        loader = PyPDFLoader(str(pdf))
        docs = loader.load()
        documents.extend(docs)
    print(f"\nLoaded {len(documents)} pages.\n")

    return documents


def split_documents(documents):
    """Split documents into smaller chunks."""

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""],
    )

    chunks = splitter.split_documents(documents)

    print(f"Created {len(chunks)} chunks.\n")

    return chunks


def create_vector_db(chunks):
    """Generate embeddings and store them inside ChromaDB."""

    # Remove old database
    db_path = Path(CHROMA_DB_DIR)

    if db_path.exists():
        shutil.rmtree(db_path)
    print("Creating Embeddings...\n")

    embeddings = OllamaEmbeddings(
        model=EMBEDDING_MODEL
    )

    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DB_DIR,
    )

    print("Vector Database Created Successfully!\n")


def preview_chunks(chunks, n=3):
    """Display a few sample chunks."""

    print("=" * 80)
    print("Sample Chunks")
    print("=" * 80)

    for i, chunk in enumerate(chunks[:n], start=1):

        print(f"\nChunk {i}")
        print("-" * 80)
        print(f"Page : {chunk.metadata.get('page')}")
        print(f"Chars: {len(chunk.page_content)}")
        print(chunk.page_content[:300])
        print("...")


def main():

    print("=" * 80)
    print("RAG INGESTION PIPELINE")
    print("=" * 80)

    documents = load_documents()

    chunks = split_documents(documents)

    preview_chunks(chunks)

    create_vector_db(chunks)

    print("=" * 80)
    print("Ingestion Completed Successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()