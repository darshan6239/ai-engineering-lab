import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import ForceGraph2D from "react-force-graph-2d";

const API_BASE = "/api";

const ROLE_LABELS = {
  id: "Identity (main node)",
  category: "Category (branches out into its own nodes)",
  property: "Property (stored on the main node)",
  ignore: "Ignore",
};

const PALETTE = ["#7FB3AB", "#C9963E", "#A87FB3", "#B37F7F", "#7F9BB3", "#93B37F", "#B3A87F"];

function colorForLabel(label) {
  let hash = 0;
  for (let i = 0; i < label.length; i++) hash = label.charCodeAt(i) + ((hash << 5) - hash);
  return PALETTE[Math.abs(hash) % PALETTE.length];
}

export default function App() {
  const [stage, setStage] = useState("upload"); // upload | mapping | explore
  const [fileId, setFileId] = useState(null);
  const [sheets, setSheets] = useState([]);
  const [sheetName, setSheetName] = useState(null);
  const [schema, setSchema] = useState(null);
  const [rowCount, setRowCount] = useState(0);
  const [datasetName, setDatasetName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]);
  const [highlightIds, setHighlightIds] = useState(new Set());
  const fgRef = useRef();

  // ---------- Stage 1: Upload ----------
  const handleFile = useCallback(async (file) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: form });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setFileId(data.file_id);
      setSheets(data.sheets);
      setDatasetName(file.name.replace(/\.(xlsx|xls|csv|tsv|ods)$/i, ""));
      if (data.sheets.length === 1) {
        await loadSchema(data.file_id, data.sheets[0]);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  const loadSchema = async (fid, sheet) => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/suggest-schema`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: fid, sheet_name: sheet }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setSheetName(sheet);
      setRowCount(data.row_count);
      setSchema(data.schema);
      setStage("mapping");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  // ---------- Stage 2: Mapping ----------
  const updateRole = (colName, role) => {
    setSchema((s) => ({
      ...s,
      columns: s.columns.map((c) => (c.name === colName ? { ...c, role } : c)),
    }));
  };

  const buildGraph = async () => {
    setBusy(true);
    setError(null);
    try {
      const idCol = schema.columns.find((c) => c.role === "id");
      const mapping = {
        primary_label: schema.primary_label,
        id_column: idCol.name,
        category_columns: schema.columns.filter((c) => c.role === "category").map((c) => c.name),
        property_columns: schema.columns.filter((c) => c.role === "property").map((c) => c.name),
      };
      const res = await fetch(`${API_BASE}/build`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_id: fileId,
          sheet_name: sheetName,
          dataset_name: datasetName,
          mapping,
          wipe: true,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      await loadGraph();
      setStage("explore");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  // ---------- Stage 3: Explore ----------
  const loadGraph = async () => {
    const res = await fetch(`${API_BASE}/graph/${encodeURIComponent(datasetName)}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    setGraphData(data);
  };

  const askQuestion = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset_name: datasetName, question }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setHistory((h) => [{ question, ...data }, ...h]);

      // Highlight nodes whose name/value appears in the returned rows
      const mentioned = new Set();
      (data.rows || []).forEach((row) => {
        Object.values(row).forEach((val) => {
          if (val && typeof val === "object") {
            const name = val.id || val.value || val.name;
            if (name) mentioned.add(String(name).toLowerCase());
          } else if (val) {
            mentioned.add(String(val).toLowerCase());
          }
        });
      });
      const ids = new Set();
      graphData.nodes.forEach((n) => {
        if (mentioned.has(String(n.name).toLowerCase())) ids.add(n.id);
      });
      setHighlightIds(ids);
      setQuestion("");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">✦</span>
          <span className="brand-name">CartoGraph</span>
        </div>
        <span className="brand-tagline">map the relationships hiding in your data</span>
      </header>

      {error && <div className="error-banner">{error}</div>}

      {stage === "upload" && (
        <UploadStage busy={busy} onFile={handleFile} sheets={sheets} onPick={(s) => loadSchema(fileId, s)} />
      )}

      {stage === "mapping" && schema && (
        <MappingStage
          schema={schema}
          rowCount={rowCount}
          datasetName={datasetName}
          setDatasetName={setDatasetName}
          updateRole={updateRole}
          onBuild={buildGraph}
          busy={busy}
        />
      )}

      {stage === "explore" && (
        <ExploreStage
          graphData={graphData}
          question={question}
          setQuestion={setQuestion}
          askQuestion={askQuestion}
          history={history}
          busy={busy}
          highlightIds={highlightIds}
          fgRef={fgRef}
        />
      )}
    </div>
  );
}

function UploadStage({ busy, onFile, sheets, onPick }) {
  return (
    <section className="stage upload-stage">
      <h1 className="hero-line">
        Every spreadsheet is <em>hiding a map</em>.
      </h1>
      <p className="hero-sub">
        Upload an Excel file. CartoGraph reads its structure, lets you confirm how rows and
        columns turn into a graph, then loads it into Neo4j so you can ask it questions in
        plain English.
      </p>

      <label className="dropzone">
        <input
          type="file"
          accept=".xlsx,.xls,.csv,.tsv,.ods"
          onChange={(e) => onFile(e.target.files[0])}
          hidden
        />
        <span className="dropzone-icon">⤒</span>
        <span>{busy ? "Reading file…" : "Click to choose a spreadsheet"}</span>
      </label>

      {sheets.length > 1 && (
        <div className="sheet-picker">
          <p>This workbook has multiple sheets — which one?</p>
          <div className="chip-row">
            {sheets.map((s) => (
              <button className="chip" key={s} onClick={() => onPick(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function MappingStage({ schema, rowCount, datasetName, setDatasetName, updateRole, onBuild, busy }) {
  const idCount = schema.columns.filter((c) => c.role === "id").length;
  const categoryCount = schema.columns.filter((c) => c.role === "category").length;

  return (
    <section className="stage mapping-stage">
      <h2 className="section-title">Confirm the map key</h2>
      <p className="section-sub">
        CartoGraph suggested a role for each column. <strong>{rowCount}</strong> rows will become{" "}
        <strong>{schema.primary_label}</strong> nodes. Adjust anything before it's written to the graph.
      </p>

      <div className="field-row">
        <label>Dataset name</label>
        <input value={datasetName} onChange={(e) => setDatasetName(e.target.value)} />
      </div>

      <table className="mapping-table">
        <thead>
          <tr>
            <th>Column</th>
            <th>Sample values</th>
            <th>Distinct</th>
            <th>Role</th>
          </tr>
        </thead>
        <tbody>
          {schema.columns.map((c) => (
            <tr key={c.name} className={c.role === "id" ? "row-id" : ""}>
              <td className="col-name">{c.name}</td>
              <td className="col-sample">{c.sample_values.slice(0, 3).join(", ")}</td>
              <td className="col-nunique">{c.nunique}</td>
              <td>
                <select value={c.role} onChange={(e) => updateRole(c.name, e.target.value)}>
                  {Object.entries(ROLE_LABELS).map(([k, label]) => (
                    <option key={k} value={k}>
                      {label}
                    </option>
                  ))}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {idCount !== 1 && (
        <p className="warning-text">Exactly one column must be marked "Identity" — currently {idCount}.</p>
      )}
      {idCount === 1 && categoryCount === 0 && (
        <p className="warning-text">
          No columns are marked "Category" — the graph will build fine, but nodes won't be
          connected to each other. Mark at least one low-cardinality column (like a type,
          region, or status) as Category to see relationships.
        </p>
      )}

      <button className="primary-btn" disabled={busy || idCount !== 1} onClick={onBuild}>
        {busy ? "Building graph…" : "Build the graph"}
      </button>
    </section>
  );
}

function ExploreStage({ graphData, question, setQuestion, askQuestion, history, busy, highlightIds, fgRef }) {
  const [hoverNode, setHoverNode] = useState(null);

  const degree = useMemo(() => {
    const d = {};
    graphData.nodes.forEach((n) => (d[n.id] = 0));
    graphData.links.forEach((l) => {
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      d[s] = (d[s] || 0) + 1;
      d[t] = (d[t] || 0) + 1;
    });
    return d;
  }, [graphData]);

  const labelColors = useMemo(() => {
    const labels = [...new Set(graphData.nodes.map((n) => n.label))];
    return labels.map((l) => ({ label: l, color: colorForLabel(l) }));
  }, [graphData]);

  const highlightLinkKeys = useMemo(() => {
    if (!highlightIds.size) return new Set();
    const keys = new Set();
    graphData.links.forEach((l) => {
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      if (highlightIds.has(s) || highlightIds.has(t)) keys.add(`${s}->${t}`);
    });
    return keys;
  }, [graphData, highlightIds]);

  // Zoom to fit once the graph first loads
  useEffect(() => {
    if (graphData.nodes.length && fgRef.current) {
      const t = setTimeout(() => fgRef.current.zoomToFit(400, 80), 300);
      return () => clearTimeout(t);
    }
  }, [graphData]);

  // Zoom to the highlighted nodes whenever a question is answered
  useEffect(() => {
    if (highlightIds.size && fgRef.current) {
      const nodes = graphData.nodes.filter((n) => highlightIds.has(n.id));
      if (nodes.length) {
        const t = setTimeout(() => {
          fgRef.current.zoomToFit(500, 100, (n) => highlightIds.has(n.id));
        }, 200);
        return () => clearTimeout(t);
      }
    }
  }, [highlightIds]);

  const nodeRadius = (node) => 4 + Math.min(Math.sqrt(degree[node.id] || 0) * 3, 16);

  const nodeColor = (node) => {
    if (highlightIds.size) return highlightIds.has(node.id) ? "#C9963E" : "rgba(74,85,104,0.25)";
    return colorForLabel(node.label);
  };

  const showLabel = (node, scale) => {
    if (hoverNode && node.id === hoverNode.id) return true;
    if (highlightIds.size) return highlightIds.has(node.id);
    return nodeRadius(node) * scale > 14; // only label nodes big enough on screen
  };

  const hasLinks = graphData.links.length > 0;

  return (
    <section className="stage explore-stage">
      <div className="graph-pane">
        {graphData.nodes.length === 0 && <div className="graph-hint">Building graph…</div>}
        {graphData.nodes.length > 0 && !hasLinks && (
          <div className="graph-hint">
            No relationships in this graph yet — go back and mark at least one column as{" "}
            <strong>Category</strong> to connect nodes together.
          </div>
        )}

        {labelColors.length > 0 && (
          <div className="graph-legend">
            {labelColors.map((l) => (
              <div className="legend-row" key={l.label}>
                <span className="legend-dot" style={{ background: l.color }} />
                {l.label}
              </div>
            ))}
          </div>
        )}

        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          backgroundColor="#0B0E14"
          nodeRelSize={1}
          nodeVal={(n) => nodeRadius(n)}
          linkColor={(l) => {
            const s = typeof l.source === "object" ? l.source.id : l.source;
            const t = typeof l.target === "object" ? l.target.id : l.target;
            return highlightLinkKeys.has(`${s}->${t}`) ? "rgba(201,150,62,0.9)" : "rgba(127,179,171,0.25)";
          }}
          linkWidth={(l) => {
            const s = typeof l.source === "object" ? l.source.id : l.source;
            const t = typeof l.target === "object" ? l.target.id : l.target;
            return highlightLinkKeys.has(`${s}->${t}`) ? 2.5 : 1;
          }}
          linkDirectionalArrowLength={3}
          nodeColor={nodeColor}
          onNodeHover={setHoverNode}
          nodeCanvasObjectMode={() => "after"}
          nodeCanvasObject={(node, ctx, scale) => {
            if (!showLabel(node, scale)) return;
            const label = node.name;
            const fontSize = 11 / scale;
            ctx.font = `${fontSize}px Inter, sans-serif`;
            ctx.fillStyle = "rgba(237,234,224,0.9)";
            ctx.textAlign = "center";
            ctx.fillText(label, node.x, node.y + nodeRadius(node) + 8 / scale);
          }}
        />
      </div>

      <div className="ask-pane">
        <form className="ask-bar" onSubmit={askQuestion}>
          <input
            placeholder="Ask a question about this data…"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <button className="primary-btn" disabled={busy} type="submit">
            {busy ? "Thinking…" : "Ask"}
          </button>
        </form>

        <div className="history">
          {history.length === 0 && (
            <p className="empty-hint">
              Try: "Which category has the most entries?" or "Show me everything linked to X."
            </p>
          )}
          {history.map((h, i) => (
            <div className="answer-card" key={i}>
              <p className="answer-question">{h.question}</p>
              <p className="answer-text">{h.answer}</p>
              {h.cypher && (
                <details>
                  <summary>Generated Cypher</summary>
                  <pre>{h.cypher}</pre>
                </details>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
