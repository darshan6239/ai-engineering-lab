"""
Takes a pandas DataFrame + a confirmed column mapping (from excel_parser.py,
edited by the user in the UI) and writes it into Neo4j as a property graph:

  (:<PrimaryLabel> {id, ...property columns})
  (:<PrimaryLabel>)-[:HAS_<CATEGORY_COLUMN>]->(:<CategoryColumn> {value})

This mirrors the "hub and spoke" shape (e.g. Biology --IN_CATEGORY--> ...):
the primary entity sits in the middle, and each low-cardinality "category"
column fans out into its own set of nodes.
"""
import re
import pandas as pd
from neo4j import GraphDatabase


def _clean_rel_name(col: str) -> str:
    rel = re.sub(r"[^A-Za-z0-9]+", "_", col).strip("_").upper()
    return f"HAS_{rel}" if rel else "HAS_VALUE"


def _clean_label(name: str) -> str:
    label = re.sub(r"[^A-Za-z0-9]+", "", name)
    return label or "Category"


class GraphBuilder:
    def __init__(self, uri: str, username: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self):
        self.driver.close()

    def wipe_database(self):
        """Danger: deletes everything. Useful when re-importing a sheet."""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def build_from_dataframe(self, df: pd.DataFrame, mapping: dict, dataset_name: str):
        """
        mapping = {
          "primary_label": "Grant",
          "id_column": "Grant ID",
          "category_columns": ["Category", "Funder"],
          "property_columns": ["Amount", "Year"],
        }
        """
        primary_label = _clean_label(mapping["primary_label"])
        id_col = mapping["id_column"]
        category_cols = mapping.get("category_columns", [])
        property_cols = mapping.get("property_columns", [])

        with self.driver.session() as session:
            session.execute_write(self._ensure_constraint, primary_label)
            session.execute_write(self._write_primary_nodes, df, primary_label, id_col, property_cols, dataset_name)
            for col in category_cols:
                session.execute_write(self._write_category_edges, df, primary_label, id_col, col)

    @staticmethod
    def _ensure_constraint(tx, primary_label: str):
        tx.run(
            f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:`{primary_label}`) REQUIRE n.id IS UNIQUE"
        )

    @staticmethod
    def _write_primary_nodes(tx, df, primary_label, id_col, property_cols, dataset_name):
        rows = []
        for _, row in df.iterrows():
            rid = row[id_col] if id_col in df.columns else None
            if rid is None or (isinstance(rid, float) and pd.isna(rid)):
                continue
            props = {}
            for p in property_cols:
                val = row.get(p)
                if pd.isna(val):
                    continue
                props[re.sub(r'[^A-Za-z0-9_]', '_', p)] = str(val) if not isinstance(val, (int, float, bool)) else val
            rows.append({"id": str(rid), "props": props})

        tx.run(
            f"""
            UNWIND $rows AS row
            MERGE (n:`{primary_label}` {{id: row.id}})
            SET n += row.props, n.dataset = $dataset_name
            """,
            rows=rows,
            dataset_name=dataset_name,
        )

    @staticmethod
    def _write_category_edges(tx, df, primary_label, id_col, category_col):
        cat_label = _clean_label(category_col)
        rel_name = _clean_rel_name(category_col)
        rows = []
        for _, row in df.iterrows():
            rid = row.get(id_col)
            cval = row.get(category_col)
            if pd.isna(rid) or pd.isna(cval):
                continue
            rows.append({"id": str(rid), "value": str(cval)})

        tx.run(
            f"""
            UNWIND $rows AS row
            MATCH (n:`{primary_label}` {{id: row.id}})
            MERGE (c:`{cat_label}` {{value: row.value}})
            MERGE (n)-[:`{rel_name}`]->(c)
            """,
            rows=rows,
        )

    def get_full_graph(self, dataset_name: str, limit: int = 500):
        """Return nodes/edges in a shape ready for react-force-graph."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n {dataset: $dataset_name})
                OPTIONAL MATCH (n)-[r]->(m)
                RETURN n, r, m
                LIMIT $limit
                """,
                dataset_name=dataset_name,
                limit=limit,
            )
            nodes = {}
            links = []
            for record in result:
                for node in filter(None, (record["n"], record["m"])):
                    key = node.element_id
                    if key not in nodes:
                        label = list(node.labels)[0] if node.labels else "Node"
                        display = node.get("id") or node.get("value") or label
                        nodes[key] = {
                            "id": key,
                            "label": label,
                            "name": str(display),
                            "isPrimary": node.get("id") is not None,
                        }

                rel = record["r"]
                if rel is not None:
                    links.append({
                        "source": rel.start_node.element_id,
                        "target": rel.end_node.element_id,
                        "type": rel.type,
                    })
            return {"nodes": list(nodes.values()), "links": links}
