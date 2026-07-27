"""
GraphRAG query engine: translates a plain-English question into Cypher,
runs it against Neo4j, then asks the LLM to explain the results in plain
English -- and returns the raw rows too, so the frontend can highlight the
relevant nodes on the force-directed graph.

Flow:
  question --(LLM: NL->Cypher)--> cypher --(Neo4j)--> rows --(LLM: explain)--> answer
"""
import json
import re
from groq import Groq
from neo4j import GraphDatabase

NL_TO_CYPHER_PROMPT = """You are an expert Neo4j Cypher query writer.

Graph schema for this dataset:
{schema}

Given a user's question about this data, write ONE Cypher query that answers it.
Rules:
- Return ONLY the Cypher query, no explanation, no markdown fences.
- Use case-insensitive matching for text, e.g. WHERE toLower(n.value) CONTAINS toLower('x')
- Always LIMIT results to 25 unless the question asks for a count.
- Prefer returning human-readable properties (id, value, name) over internal ids.
- Avoid UNION unless absolutely necessary; prefer OPTIONAL MATCH / WITH instead.
- Keep the query as simple as possible while still answering the question.

Question: {question}

Cypher query:"""

EXPLAIN_PROMPT = """You are a data analyst explaining query results to a colleague.

The user asked: "{question}"

The graph database returned these rows (JSON):
{rows}

Write a concise, plain-English answer (2-6 sentences, or a short bullet list if
several items are returned). Reference actual values from the results. If the
results are empty, say so plainly and suggest a rephrase."""

FIX_CYPHER_PROMPT = """This Cypher query failed against Neo4j:

{cypher}

Error from Neo4j:
{error}

Graph schema:
{schema}

Write a corrected Cypher query that answers the original question: "{question}"
Return ONLY the corrected Cypher query, no explanation, no markdown fences."""


class QueryEngine:
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, groq_api_key, model="openai/gpt-oss-120b"):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.client = Groq(api_key=groq_api_key)
        self.model = model

    def close(self):
        self.driver.close()

    def ask(self, question: str, schema_description: str, verbose: bool = False) -> dict:
        cypher = self._nl_to_cypher(question, schema_description)
        rows, error = self._try_run(cypher)

        if error:
            cypher = self._fix_cypher(question, cypher, error, schema_description)
            rows, error = self._try_run(cypher)

        if error:
            return {
                "answer": (
                    f"The generated Cypher query still failed after a retry: {error}\n"
                    f"Try rephrasing your question."
                ),
                "cypher": cypher,
                "rows": [],
                "error": error,
            }

        answer = self._explain(question, rows)
        return {"answer": answer, "cypher": cypher, "rows": rows, "error": None}

    def _try_run(self, cypher: str):
        try:
            return self._run_cypher(cypher), None
        except Exception as e:
            return None, str(e)

    def _fix_cypher(self, question, cypher, error, schema) -> str:
        prompt = FIX_CYPHER_PROMPT.format(cypher=cypher, error=error, schema=schema, question=question)
        response = self.client.chat.completions.create(
            model=self.model, max_tokens=500, messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content.strip()
        return re.sub(r"^```(?:cypher)?\s*|\s*```$", "", raw, flags=re.IGNORECASE).strip()

    def _nl_to_cypher(self, question: str, schema: str) -> str:
        prompt = NL_TO_CYPHER_PROMPT.format(schema=schema, question=question)
        response = self.client.chat.completions.create(
            model=self.model, max_tokens=500, messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content.strip()
        return re.sub(r"^```(?:cypher)?\s*|\s*```$", "", raw, flags=re.IGNORECASE).strip()

    def _run_cypher(self, cypher: str) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(cypher)
            return [dict(record) for record in result]

    def _explain(self, question: str, rows: list[dict]) -> str:
        prompt = EXPLAIN_PROMPT.format(question=question, rows=json.dumps(rows, indent=2, default=str)[:6000])
        response = self.client.chat.completions.create(
            model=self.model, max_tokens=600, messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()


def build_schema_description(primary_label: str, category_columns: list[str], property_columns: list[str]) -> str:
    node_lines = [f"  (:{primary_label} {{id, dataset, {', '.join(property_columns) if property_columns else '...'}}})"]
    rel_lines = []

    for col in category_columns:
        label = re.sub(r"[^A-Za-z0-9]", "", col) or "Category"
        rel = re.sub(r"[^A-Za-z0-9]+", "_", col).strip("_").upper()
        rel = rel or "VALUE"
        node_lines.append(f"  (:{label} {{value}})")
        rel_lines.append(f"  (:{primary_label})-[:HAS_{rel}]->(:{label})")

    lines = ["Nodes:"] + node_lines
    if rel_lines:
        lines += ["", "Relationships:"] + rel_lines
    return "\n".join(lines)
