"""
Turns a spreadsheet into a graph schema *suggestion* using deterministic,
explainable heuristics -- no LLM guessing here, so the same file always
produces the same suggested mapping. The user confirms/edits the mapping
in the UI before anything is written to Neo4j.

Heuristic used per column:
  - "id"        : near-unique text/number column (>= 90% unique values).
                  There should be exactly one of these -- it becomes the
                  identity of the primary node.
  - "category"  : low-cardinality text column (<= configurable threshold,
                  default 50% unique, and <= 200 distinct values). Becomes
                  its own node type, connected to the primary node via a
                  HAS_<COLUMN> relationship. This is what produces the
                  hub-and-spoke graph (like the Biology -> IN_CATEGORY -> ...
                  example screenshot).
  - "property"  : everything else (numbers, dates, free text). Stored as a
                  property on the primary node, not turned into a node.
"""
from dataclasses import dataclass, field
import pandas as pd


CATEGORY_UNIQUE_RATIO_MAX = 0.5
CATEGORY_MAX_DISTINCT = 200
ID_UNIQUE_RATIO_MIN = 0.9


@dataclass
class ColumnSuggestion:
    name: str
    role: str            # "id" | "category" | "property" | "ignore"
    nunique: int
    dtype: str
    sample_values: list = field(default_factory=list)


@dataclass
class SchemaSuggestion:
    sheet_name: str
    primary_label: str
    columns: list[ColumnSuggestion]

def _engine_for(file_path: str) -> str | None:
    ext = file_path.lower().rsplit(".", 1)[-1]
    if ext == "xls":
        return "xlrd"
    if ext in ("xlsx", "xlsm"):
        return "openpyxl"
    if ext == "ods":
        return "odf"
    raise ValueError(
        f"Unsupported file extension '.{ext}'. "
        "Please upload a .xlsx, .xlsm, .xls, .ods, .csv, or .tsv file."
    )


def _is_delimited(file_path: str) -> str | None:
    """Returns the delimiter if this is a CSV/TSV file, else None."""
    ext = file_path.lower().rsplit(".", 1)[-1]
    if ext == "csv":
        return ","
    if ext == "tsv":
        return "\t"
    return None


def load_sheet(file_path: str, sheet_name: str | None = None) -> pd.DataFrame:
    delimiter = _is_delimited(file_path)
    if delimiter is not None:
        df = pd.read_csv(file_path, sep=delimiter)
    else:
        xls = pd.ExcelFile(file_path, engine=_engine_for(file_path))
        sheet = sheet_name or xls.sheet_names[0]
        df = xls.parse(sheet)

    df.columns = [str(c).strip() for c in df.columns]
    return df.dropna(how="all")


def list_sheets(file_path: str) -> list[str]:
    if _is_delimited(file_path) is not None:
        return ["Sheet1"]  # CSV/TSV files have no sheet concept — use a placeholder
    return pd.ExcelFile(file_path, engine=_engine_for(file_path)).sheet_names

def suggest_schema(df: pd.DataFrame, sheet_name: str) -> SchemaSuggestion:
    n_rows = max(len(df), 1)
    columns: list[ColumnSuggestion] = []
    id_candidates: list[tuple[str, float]] = []

    for col in df.columns:
        series = df[col].dropna()
        nunique = series.nunique()
        ratio = nunique / n_rows
        dtype = str(df[col].dtype)
        sample = [str(v) for v in series.unique()[:5]]

        is_text = dtype == "object"
        role = "property"

        if ratio >= ID_UNIQUE_RATIO_MIN and (is_text or "int" in dtype):
            role = "id"
            id_candidates.append((col, ratio))
        elif is_text and ratio <= CATEGORY_UNIQUE_RATIO_MAX and nunique <= CATEGORY_MAX_DISTINCT and nunique > 1:
            role = "category"

        columns.append(ColumnSuggestion(name=col, role=role, nunique=nunique, dtype=dtype, sample_values=sample))

    # Only keep the single best "id" candidate (highest uniqueness); demote the rest to property
    if id_candidates:
        best_id = max(id_candidates, key=lambda x: x[1])[0]
        for c in columns:
            if c.role == "id" and c.name != best_id:
                c.role = "property"
    else:
        # Fall back: no near-unique column found, use the row index as identity
        columns.insert(0, ColumnSuggestion(name="__row_id__", role="id", nunique=n_rows, dtype="int64", sample_values=[]))

    primary_label = _singularize(sheet_name)
    return SchemaSuggestion(sheet_name=sheet_name, primary_label=primary_label, columns=columns)

def _singularize(name: str) -> str:
    name = name.strip().replace(" ", "").replace("-", "")
    if name.lower().endswith("ies"):
        return name[:-3] + "y"
    if name.lower().endswith("s") and not name.lower().endswith("ss"):
        return name[:-1]
    return name or "Entity"

def schema_to_dict(s: SchemaSuggestion) -> dict:
    return {
        "sheet_name": s.sheet_name,
        "primary_label": s.primary_label,
        "columns": [
            {
                "name": c.name,
                "role": c.role,
                "nunique": c.nunique,
                "dtype": c.dtype,
                "sample_values": c.sample_values,
            }
            for c in s.columns
        ],
    }
