"""
CartoGraph API -- turns spreadsheets into explorable, queryable knowledge
graphs.

Endpoints:
  POST /api/upload            -> save file, return sheet names
  POST /api/suggest-schema     -> heuristic column-role suggestion for a sheet
  POST /api/build              -> write the (user-confirmed) mapping into Neo4j
  POST /api/ask                 -> NL question -> Cypher -> answer + rows
  GET  /api/graph/{dataset}     -> full graph for visualization
"""
import os
import re
import uuid

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from excel_parser import load_sheet, list_sheets, suggest_schema, schema_to_dict
from graph_builder import GraphBuilder
from query_engine import QueryEngine, build_schema_description

app = FastAPI(title="CartoGraph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# in-memory registry: dataset_name -> {"file_path", "mapping"}
DATASETS: dict[str, dict] = {}


class SheetRequest(BaseModel):
    file_id: str
    sheet_name: str


class BuildRequest(BaseModel):
    file_id: str
    sheet_name: str
    dataset_name: str
    mapping: dict  # {primary_label, id_column, category_columns, property_columns}
    wipe: bool = False


class AskRequest(BaseModel):
    dataset_name: str
    question: str


def _sanitize_prop(name: str) -> str:
    """Must exactly match the sanitization graph_builder.py applies when it
    writes property columns into Neo4j, so the LLM is told the *real*
    property names that actually exist on the nodes."""
    return re.sub(r'[^A-Za-z0-9_]', '_', name)


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".xlsx", ".xlsm", ".xls", ".ods", ".csv", ".tsv"):
        raise HTTPException(
            400,
            f"Unsupported file type '{ext}'. Please upload a .xlsx, .xls, .ods, .csv, or .tsv file."
        )

    file_id = str(uuid.uuid4())
    dest = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")

    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Uploaded file is empty.")

    with open(dest, "wb") as f:
        f.write(contents)

    try:
        sheets = list_sheets(dest)
    except Exception as e:
        raise HTTPException(400, f"Could not read Excel file: {e}")

    return {"file_id": file_id, "file_path": dest, "sheets": sheets}


@app.post("/api/suggest-schema")
async def suggest(req: SheetRequest):
    file_path = _resolve_file_path(req.file_id)
    df = load_sheet(file_path, req.sheet_name)
    suggestion = suggest_schema(df, req.sheet_name)
    return {"row_count": len(df), "schema": schema_to_dict(suggestion)}


@app.post("/api/build")
async def build(req: BuildRequest):
    file_path = _resolve_file_path(req.file_id)
    df = load_sheet(file_path, req.sheet_name)

    builder = GraphBuilder(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
    try:
        if req.wipe:
            builder.wipe_database()
        builder.build_from_dataframe(df, req.mapping, req.dataset_name)
    except Exception as e:
        raise HTTPException(500, f"Failed to build graph: {e}")
    finally:
        builder.close()

    DATASETS[req.dataset_name] = {"file_path": file_path, "mapping": req.mapping}
    return {"status": "ok", "dataset_name": req.dataset_name, "rows_processed": len(df)}


@app.post("/api/ask")
async def ask(req: AskRequest):
    dataset = DATASETS.get(req.dataset_name)
    if not dataset:
        raise HTTPException(404, "Dataset not found. Build the graph first.")

    mapping = dataset["mapping"]

    # IMPORTANT: property column names must be sanitized the same way
    # graph_builder.py sanitizes them before writing to Neo4j (spaces etc.
    # become underscores). Otherwise the LLM writes Cypher referencing
    # properties that don't actually exist on the nodes, and silently gets
    # no data back for those fields.
    sanitized_properties = [_sanitize_prop(p) for p in mapping.get("property_columns", [])]

    schema_description = build_schema_description(
        mapping["primary_label"], mapping.get("category_columns", []), sanitized_properties
    )

    if not settings.groq_api_key:
        raise HTTPException(400, "GROQ_API_KEY is not set on the server -- required to ask questions.")

    engine = QueryEngine(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password, settings.groq_api_key)
    try:
        result = engine.ask(req.question, schema_description)
    finally:
        engine.close()

    return result


@app.get("/api/graph/{dataset_name}")
async def graph(dataset_name: str, limit: int = 500):
    if dataset_name not in DATASETS:
        raise HTTPException(404, "Dataset not found. Build the graph first.")

    builder = GraphBuilder(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
    try:
        data = builder.get_full_graph(dataset_name, limit=limit)
    finally:
        builder.close()
    return data


def _resolve_file_path(file_id: str) -> str:
    for fname in os.listdir(UPLOAD_DIR):
        if fname.startswith(file_id):
            return os.path.join(UPLOAD_DIR, fname)
    raise HTTPException(404, "Uploaded file not found.")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
