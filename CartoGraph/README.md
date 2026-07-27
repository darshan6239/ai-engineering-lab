# CartoGraph

**Turn any spreadsheet into an explorable, queryable knowledge graph — no schema design required.**

Upload an Excel/CSV file → CartoGraph deterministically suggests how rows and columns should become graph nodes and relationships → you confirm or edit the mapping → it's written into Neo4j → ask questions in plain English and watch the answer highlight itself on a live, force-directed graph.

A full-stack **GraphRAG** application built with **React, FastAPI, Neo4j, and Groq (LLM)**.

---

## Why this project exists

Most spreadsheets contain relationships that never get modeled — a "Category" column, a "Region" column, a "Dealer" column are all implicit foreign keys to something, but nobody ever draws that graph. CartoGraph automates that first, tedious step of turning tabular data into a real graph structure, and then lets you interrogate that graph conversationally instead of writing Cypher by hand.

```
Excel / CSV file
      │   (deterministic heuristics: uniqueness ratio + cardinality)
      ▼
Suggested schema  ──user confirms/edits──▶  Neo4j graph
                                                  │
                         "which category has      │
                          the most entries?"      ▼
                                           LLM: NL → Cypher
                                                  │
                                                  ▼
                                           Neo4j executes query
                                                  │
                                                  ▼
                                     LLM: rows → plain-English answer
                                                  │
                                                  ▼
                               Answer + matching nodes highlighted on graph
```

## Screenshots

- **Landing page** — clean upload screen, no configuration required to get started
<img width="1919" height="881" alt="Screenshot 2026-07-26 231346" src="https://github.com/user-attachments/assets/2b194e17-a8f1-440e-bdb2-2724921831f2" />

- **Explore & Ask** — a hub-and-spoke graph auto-clusters by category, with a color-coded legend and live natural-language search over the data
<img width="1881" height="881" alt="Screenshot 2026-07-26 231658" src="https://github.com/user-attachments/assets/1f84a818-e7c0-4860-86bd-564cf6c1f1f8" />

- **Confirm Mapping** — every column gets a suggested role (Identity / Category / Property) that you can override before anything is written to the graph
<img width="1893" height="878" alt="Screenshot 2026-07-26 231518" src="https://github.com/user-attachments/assets/98022517-d3a2-46f3-885c-109c004f6e05" />

---

## Key design decisions

**1. The Excel → graph mapping is rule-based, not LLM-guessed.**
Every column is classified by a simple, explainable heuristic:
- **Near-unique column** (≥90% unique values) → becomes the node's **identity**
- **Low-cardinality text column** (≤50% unique, ≤200 distinct values) → becomes its own **node type**, connected via a `HAS_<COLUMN>` relationship — this produces the hub-and-spoke shape
- **Everything else** (free text, continuous numbers, dates) → stored as a **property** on the primary node

This means the same file always produces the same graph. That's deliberate: a predictable, auditable pipeline beats an LLM silently inventing a different schema every run.

**2. The LLM's job is scoped narrowly: language, not data modeling.**
Groq (via `openai/gpt-oss-120b`) is only ever asked to translate a natural-language question into Cypher, and to translate Cypher results back into plain English. It never decides what the graph *looks like* — a much safer, more reliable division of labor than asking an LLM to design a schema from scratch.

**3. Accuracy-first prompting for a known failure mode.**
Aggregation questions ("which car sold the most units") are genuinely ambiguous once one row = one listing rather than one product. The NL→Cypher prompt explicitly teaches the model to recognize when a question is really asking about a *category* (sum/count grouped by the connected node) versus a *single row*, with a worked example of the correct `WITH ... SUM(...) GROUP BY` pattern versus the naive, wrong "sort primary nodes and take the top one" pattern.

**4. Deterministic outputs, not a dice roll.**
All three LLM calls (NL→Cypher, Cypher repair, result explanation) run at `temperature=0`. A data tool that gives a different answer to the same question on two different runs isn't trustworthy — determinism was treated as a correctness requirement, not a nice-to-have.

**5. Silent failures are treated as failures.**
An empty query result and a *malformed* query that happens to return nothing look identical to a naive pipeline. CartoGraph retries once whenever a query returns zero rows — not just when Neo4j throws an outright error — so a mistyped property name doesn't get quietly reported back to the user as "no data found."

**6. Property-name consistency across the write and read paths.**
Column names get sanitized (e.g. `"Units Sold"` → `Units_Sold`) before being written to Neo4j. The schema description sent to the LLM is generated from that *same* sanitized name, so the model never writes Cypher referencing a property that doesn't actually exist in the database — a subtle but critical source of wrong answers in early versions.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite, `react-force-graph-2d` for the interactive graph |
| Backend | FastAPI (Python) |
| Graph database | Neo4j (AuraDB free tier) |
| LLM | Groq (`openai/gpt-oss-120b`) |
| Data parsing | pandas, openpyxl, xlrd, odfpy |

## Project structure

```
cartograph/
├── backend/
│   ├── main.py            # FastAPI app: upload / suggest-schema / build / ask / graph
│   ├── excel_parser.py     # Heuristic column-role suggestion, multi-format file reading
│   ├── graph_builder.py    # Writes DataFrame + mapping into Neo4j
│   ├── query_engine.py     # NL -> Cypher -> Neo4j -> NL (GraphRAG core)
│   ├── config.py           # Loads .env credentials
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.jsx         # Upload -> mapping confirmation -> explore
    │   └── App.css
    └── package.json
```

## Features

- **Multi-format ingestion** — `.xlsx`, `.xlsm`, `.xls`, `.ods`, `.csv`, and `.tsv`, each parsed with the correct engine rather than relying on pandas to guess file format from raw bytes
- **Editable schema suggestions** — every column's suggested role (Identity / Category / Property / Ignore) can be overridden in the UI before anything is written
- **Interactive force-directed graph** — node size scales with connection count, node color is consistent per entity type with an on-screen legend, and labels only render for prominent or highlighted nodes to avoid visual clutter
- **Natural-language querying** — ask questions like *"which category has the most entries?"* or *"show me everything linked to X"* and get a plain-English answer plus the generated Cypher (shown collapsed, for transparency)
- **Live highlight-on-answer** — asking a question dims the graph and highlights + auto-zooms to the specific nodes and edges that answered it

## Setup

### 1. Neo4j (free, cloud-hosted)
Sign up at [console.neo4j.io](https://console.neo4j.io/), create a free **AuraDB** instance, and copy the connection URI, username, and password.

### 2. Groq API key (free)
Get one at [console.groq.com/keys](https://console.groq.com/keys) — no credit card required.

### 3. Backend
```bash
cd backend
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env   # fill in your Neo4j + Groq credentials
uvicorn main:app --reload --port 8000
```

### 4. Frontend
```bash
cd frontend
npm install
npm run dev
```
Open **http://localhost:5173** — the Vite dev server proxies `/api` requests to the backend on port 8000.

## Try it

Any spreadsheet with a mix of an ID-like column (name, SKU, listing number) and a few low-cardinality columns (category, status, region, department) produces a clear hub-and-spoke graph. Example questions:

- *"Which category has the most entries?"*
- *"Show me everything linked to `<value>`."*
- *"How many distinct `<category>` are there?"*
- *"Which `<category>` has the highest total `<numeric property>`?"*

## Possible extensions

- Multi-sheet joins (linking two sheets via a shared ID column)
- Persistent dataset storage instead of an in-memory registry (currently reset on backend restart)
- Auth + per-user datasets
- Export the current graph view as an image/PDF
- Swap Groq for another provider by changing one line in `query_engine.py`

## License

MIT
