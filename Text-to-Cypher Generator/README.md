# Text-to-Cypher Generator

A Streamlit app that converts natural language questions into production-ready **Neo4j Cypher** queries, using a locally running **Ollama** model via **LangChain**. Fully local — no data leaves your machine, no API keys required.

<img width="1888" height="899" alt="Screenshot 2026-07-12 010108" src="https://github.com/user-attachments/assets/a56ccb51-e1ab-4be9-b3b4-88c8561f9c29" />

## Features

- **Natural language → Cypher** — describe what you want in plain English and get a ready-to-run Cypher query.
- **Runs fully locally** — powered by [Ollama](https://ollama.com), so your questions and data never leave your machine.
- **Multiple model support** — switch between `qwen2.5:1.5b`, `qwen2.5:3b`, `llama3.2`, `deepseek-r1:8b`, and `gemma3` from the sidebar.
- **Schema inference from your own data** — upload one CSV per node type (e.g. `employees.csv`, `companies.csv`) and the app infers node labels and properties directly from your columns, instead of relying on a generic example schema.
- **Prompt presets** — bias generation toward common graph types (Movies, HR, E-Commerce, Social Network, Knowledge Graph, or General).
- **Generation controls** — cap the number of returned records and optionally auto-append a `LIMIT` clause.
- **Prompt transparency** — optionally view the exact rendered prompt sent to the model.
- **Query tooling** — view stats (characters/words/lines), copy the query, download it as a `.cypher` file, and inspect the raw model output.
- **Query history** — the last 10 questions are kept in the sidebar for the session.
- **Cypher syntax reference** — a built-in expander with common query patterns.

## Screenshots

**Describing a question and generating a query:**

<img width="1871" height="817" alt="Screenshot 2026-07-12 010159" src="https://github.com/user-attachments/assets/61e5192e-31b4-4d3f-960d-1d7e856054f3" />


**Reviewing, copying, and downloading the result:**

<img width="1896" height="900" alt="Screenshot 2026-07-12 010224" src="https://github.com/user-attachments/assets/2c84f723-01a3-4c2f-96c9-4fa1d84afb0e" />


## Requirements

- Python 3.9+
- [Ollama](https://ollama.com) installed and running locally, with at least one supported model pulled, e.g.:
  ```bash
  ollama pull qwen2.5:1.5b
  ```
- Python packages:
  ```bash
  pip install streamlit langchain-ollama langchain-core pandas
  ```

## Installation

```bash
git clone <this-repo-url>
cd <this-repo>
pip install streamlit langchain-ollama langchain-core pandas
```

Make sure Ollama is running in the background before starting the app:

```bash
ollama serve
```

## Usage

```bash
streamlit run app.py
```

Then open the URL Streamlit prints (typically `http://localhost:8501`).

1. **(Optional) Upload your data** — in the "Upload Your Data" section, upload one CSV per node type. The filename becomes the node label and the columns become its properties. Skip this to use the built-in generic schema.
2. **Configure generation** in the sidebar — choose a model, temperature, graph type preset, max records, and whether to auto-append `LIMIT`.
3. **Describe your query** in plain English in the text box.
4. Click **Generate Cypher Query**.
5. Review the result, check the query stats, copy it, or download it as a `.cypher` file.

## Configuration Reference

| Setting | Location | Description |
|---|---|---|
| Ollama Model | Sidebar | Which local model generates the query |
| Temperature | Sidebar | Randomness of generation (`0.0` = deterministic) |
| Graph Type | Sidebar | Prompt preset hint for the target domain |
| Maximum Returned Records | Sidebar | Value used in the generated `LIMIT` clause |
| Append LIMIT clause | Sidebar | Toggles whether `LIMIT` is added at all |
| Show Prompt | Sidebar | Displays the fully rendered prompt sent to the model |
| Upload CSV files | Main panel | Infers real schema (labels + properties) from your data |

## Project Structure

```
.
├── app.py                          # Streamlit application
├── README.md
└── assets/
    └── screenshots/
        ├── 01-home-and-upload.png
        ├── 02-generated-query.png
        └── 03-output-tools.png
```

## Notes & Limitations

- This app **generates** Cypher only — it does not execute queries against a Neo4j database. Always review a generated query before running it in the Neo4j Browser or driver.
- Without an uploaded schema, the model works off a generic example schema (`Person`, `Company`, `Movie`, etc.) and may not match your actual graph.
- Smaller/faster models (e.g. `qwen2.5:1.5b`) respond quicker; reasoning models (e.g. `deepseek-r1:8b`) are slower but may reason more carefully about complex questions.
- The model must already be pulled in Ollama (`ollama pull <model>`) before selecting it in the sidebar.

## Roadmap

- [ ] Optional live connection to Neo4j to pull the real schema automatically (`CALL db.schema.visualization()`), instead of relying on CSV uploads.
- [ ] In-app query execution against a connected Neo4j instance.
- [ ] Streaming token-by-token output for faster perceived response time.

## Credits

Built with **Streamlit** • **LangChain** • **Ollama** • **Cypher**

**Darshan Patil** — AI Engineer • Artificial Intelligence & Data Science
