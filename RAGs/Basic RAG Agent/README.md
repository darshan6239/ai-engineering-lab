# Basic RAG Agent

A simple local RAG (Retrieval-Augmented Generation) app: ingest PDFs into a
Chroma vector store, then ask questions answered only from that content, via
a Streamlit UI. Runs fully locally using [Ollama](https://ollama.com).

## Preview

**Empty state — ready to ask a question:**

<img width="1470" height="461" alt="Screenshot 2026-07-13 003117" src="https://github.com/user-attachments/assets/09597c94-aa02-4abe-9577-428975907f61" />

**After asking a question — answer with cited sources:**

<img width="1783" height="723" alt="Screenshot 2026-07-13 003019" src="https://github.com/user-attachments/assets/7cdbfb6e-417b-4303-89ec-6a35992f5efd" />

## Setup

1. **Install Ollama** and pull the required models:
   ```bash
   ollama pull qwen2.5:1.5b
   ollama pull nomic-embed-text
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Add your PDFs** to `./data/pdfs/` (create the folder if needed).

## Usage

1. **Ingest documents** (run once, or whenever your PDFs change):
   ```bash
   python ingest.py
   ```
   This loads the PDFs, splits them into chunks, and stores embeddings in
   `./chroma_db`.

2. **Launch the app**:
   ```bash
   streamlit run app.py
   ```
   Then open the URL Streamlit prints (usually http://localhost:8501) and
   start asking questions.

## Configuration

Edit `config.py` to change models, chunk size, overlap, or how many chunks
are retrieved per question (`TOP_K`).

## Notes

- If you see an error about a missing vector database, run `python ingest.py` first.
- If you see connection errors, make sure `ollama serve` is running and the
  models above are pulled.
