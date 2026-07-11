import time
import streamlit as st
import pandas as pd
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------

st.set_page_config(
    page_title="Text-to-Cypher Generator",
    page_icon="🔗",
    layout="wide"
)

# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

if "history" not in st.session_state:
    st.session_state.history = []

# --------------------------------------------------
# CUSTOM CSS
# --------------------------------------------------

st.markdown("""
<style>

.stApp{
background:
radial-gradient(circle at top,
#111827 0%,
#0b1220 45%,
#050814 100%);
}

.hero{
padding:35px;
border-radius:18px;
background:linear-gradient(
135deg,
rgba(59,130,246,.18),
rgba(99,102,241,.18)
);
border:1px solid rgba(255,255,255,.08);
margin-bottom:25px;
}

.hero h1{
font-size:42px;
font-weight:700;
color:white;
margin-bottom:10px;
}

.hero p{
font-size:17px;
color:#cbd5e1;
line-height:1.6;
}

.block{
padding:20px;
border-radius:15px;
background:rgba(255,255,255,.04);
border:1px solid rgba(255,255,255,.08);
margin-top:20px;
}

.stButton>button{
width:100%;
height:52px;
border-radius:10px;
font-size:17px;
font-weight:600;
background:#2563eb;
color:white;
border:none;
}

.stButton>button:hover{
background:#1d4ed8;
}

.footer{
text-align:center;
margin-top:60px;
padding-top:25px;
border-top:1px solid rgba(255,255,255,.08);
}

.footer-name{
font-size:24px;
font-weight:700;
color:white;
}

.footer-role{
font-size:17px;
color:#cbd5e1;
margin-bottom:20px;
}

.footer-note{
color:#94a3b8;
font-size:14px;
}

</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# SIDEBAR — CONFIGURATION (all controls defined up-front,
# before anything below tries to use them)
# --------------------------------------------------

with st.sidebar:

    st.title("Configuration")

    model_name = st.selectbox(
        "Ollama Model",
        [
            "qwen2.5:1.5b",
            "qwen2.5:3b",
            "llama3.2",
            "deepseek-r1:8b",
            "gemma3"
        ],
        index=0
    )

    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=0.0,
        step=0.1
    )

    st.divider()

    st.subheader("Prompt Presets")

    preset = st.selectbox(
        "Graph Type",
        [
            "General",
            "Movies",
            "HR",
            "E-Commerce",
            "Social Network",
            "Knowledge Graph"
        ]
    )

    st.divider()

    st.subheader("Generation")

    top_k = st.slider(
        "Maximum Returned Records",
        5,
        100,
        25
    )

    include_limit = st.checkbox(
        "Append LIMIT clause",
        value=True
    )

    show_prompt = st.checkbox(
        "Show Prompt",
        value=False
    )

    st.divider()

    st.subheader("About")

    st.caption("""
This application converts
Natural Language into
Neo4j Cypher using
a locally running
Ollama model.
""")

    st.divider()

    st.subheader("History")

    if st.session_state.history:
        for item in reversed(st.session_state.history[-10:]):
            st.caption(item)
    else:
        st.caption("No queries generated.")

# --------------------------------------------------
# HERO SECTION
# --------------------------------------------------

st.markdown("""
<div class="hero">

<h1>Text-to-Cypher Generator</h1>

<p>

Generate production-ready Neo4j Cypher queries
from natural language using a locally running
Ollama model.

</p>

</div>
""", unsafe_allow_html=True)

# --------------------------------------------------
# DASHBOARD METRICS
# --------------------------------------------------

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Model", model_name)

with col2:
    st.metric("Query Language", "Cypher")

with col3:
    st.metric("Execution", "Generation Only")

st.divider()

# --------------------------------------------------
# DATA UPLOAD (schema inference)
# --------------------------------------------------
# Previously the app only knew about a hardcoded, generic schema
# (Person/Company/Movie...). Real graphs rarely match that guess.
# Here you can upload one or more CSVs — each file is treated as one
# node label, and its columns become that node's properties, so the
# generated Cypher actually matches your data instead of a generic
# assumption.

st.subheader("Upload Your Data (optional)")

st.caption(
    "Upload one CSV per node type — e.g. employees.csv, companies.csv. "
    "The filename becomes the node label and the columns become its "
    "properties. If nothing is uploaded, a generic example schema is used instead."
)

uploaded_files = st.file_uploader(
    "Upload CSV files",
    type=["csv"],
    accept_multiple_files=True
)

inferred_schema_parts = []

if uploaded_files:

    for file in uploaded_files:

        try:
            df = pd.read_csv(file)
        except Exception as e:
            st.error(f"Could not read {file.name}: {e}")
            continue

        label = "".join(
            part.capitalize() for part in file.name.rsplit(".", 1)[0].replace("-", "_").split("_")
        ) or file.name

        columns = list(df.columns)

        inferred_schema_parts.append(
            f"({label}) properties: {', '.join(columns)}"
        )

        with st.expander(f"Preview: {file.name}  →  inferred label `{label}`"):
            st.dataframe(df.head(10), use_container_width=True)
            st.caption(f"{len(df)} rows • {len(columns)} columns")

if inferred_schema_parts:
    custom_schema = "Node types inferred from uploaded data:\n\n" + "\n".join(inferred_schema_parts)
    st.success(f"Using schema inferred from {len(uploaded_files)} uploaded file(s) instead of the generic example schema.")
else:
    custom_schema = ""

st.divider()

# --------------------------------------------------
# MAIN INPUT (this was completely missing before —
# `question` and `generate` were referenced but never created)
# --------------------------------------------------

question = st.text_area(
    "Describe the query you want in natural language",
    placeholder="e.g. Find all employees who work at companies located in California",
    height=120
)

generate = st.button("Generate Cypher Query")

# --------------------------------------------------
# OLLAMA MODEL
# --------------------------------------------------
# SPEED FIX 1 — this used to build a brand-new ChatOllama client on
# every single Streamlit rerun (every widget click reruns the whole
# script), which redoes connection setup each time. st.cache_resource
# builds it once per (model, temperature) combo and reuses it.
#
# SPEED FIX 2 — num_predict caps how many tokens the model may
# generate. Without it, a small local model can ramble well past a
# one-line Cypher query, and every extra token costs real time.
#
# SPEED FIX 3 — keep_alive tells Ollama to keep the model loaded in
# memory for longer. Ollama's default is 5 minutes; if you pause
# between queries the model gets unloaded, and the next query pays a
# slow reload penalty. "30m" avoids that during normal interactive use.

@st.cache_resource(show_spinner=False)
def get_llm(model_name: str, temperature: float) -> ChatOllama:
    return ChatOllama(
        model=model_name,
        temperature=temperature,
        num_predict=256,
        keep_alive="30m"
    )

llm = get_llm(model_name, temperature)

# --------------------------------------------------
# PROMPT TEMPLATE (single, merged version — combines the
# schema hints from the first template with the preset /
# limit logic from the second one that used to be dead code)
# --------------------------------------------------

limit_instruction = (
    f"Append LIMIT {top_k} when appropriate."
    if include_limit
    else "Do NOT append a LIMIT clause."
)

# If the user uploaded CSVs, use the real inferred schema and tell the
# model to prioritize it over any generic assumptions. Otherwise fall
# back to the original generic example schema so the app still works
# with no upload.
if custom_schema:
    schema_section = f"""
Use ONLY the following real schema, inferred from the user's uploaded data.
Do not invent labels, relationships, or properties outside of this schema
unless the question clearly requires a relationship between two of these
node types, in which case pick a reasonable relationship name in
UPPER_SNAKE_CASE.

{custom_schema}
"""
else:
    schema_section = """
No custom data was uploaded, so assume the graph can contain labels such as:

Person
Employee
Company
Department
Project
Skill
Customer
Product
Order
Movie
Actor
Director
Book
Author

Relationships may include:

WORKS_AT
WORKS_ON
HAS_SKILL
MANAGES
PURCHASED
BELONGS_TO
FRIEND_OF
ACTED_IN
DIRECTED
WRITTEN_BY
LOCATED_IN
"""

prompt = ChatPromptTemplate.from_template("""
You are a senior Neo4j Architect and expert Cypher developer.

Your task is to convert natural language into a valid,
production-ready Neo4j Cypher query.

Rules:

- Return ONLY the Cypher query.
- Do NOT explain anything.
- Do NOT use markdown.
- Do NOT wrap the answer in ``` blocks.
- Do NOT add comments.
- Generate clean, optimized Cypher.
- Use aliases whenever appropriate.
- Use MATCH as the primary clause.
- Use WHERE for filtering.
- Use ORDER BY and RETURN whenever required.
- {limit_instruction}

{schema_section}

Graph Type:

{preset}

Natural Language:

{question}

Cypher:
""")

# --------------------------------------------------
# LANGCHAIN PIPELINE (built once, from the final prompt)
# --------------------------------------------------

cypher_chain = (
    prompt
    | llm
    | StrOutputParser()
)

if show_prompt:
    with st.expander("View Rendered Prompt", expanded=True):
        st.code(
            prompt.format(
                preset=preset,
                question=question if question.strip() else "<your question here>",
                limit_instruction=limit_instruction,
                schema_section=schema_section
            ),
            language="text"
        )

# --------------------------------------------------
# HELPER FUNCTION
# --------------------------------------------------

def clean_cypher(query: str) -> str:
    query = query.replace("```cypher", "")
    query = query.replace("```", "")
    query = query.strip()
    return query

# SPEED FIX 4 — if someone re-runs the exact same question with the
# same settings (easy to do while testing), there's no reason to hit
# the model again. st.cache_data memoizes the result so a repeat
# request returns instantly instead of re-generating from scratch.

@st.cache_data(show_spinner=False)
def generate_cypher_cached(question: str, preset: str, limit_instruction: str,
                            model_name: str, temperature: float, schema_section: str) -> str:
    raw_output = cypher_chain.invoke(
        {
            "question": question,
            "preset": preset,
            "limit_instruction": limit_instruction,
            "schema_section": schema_section
        }
    )
    return raw_output

# --------------------------------------------------
# GENERATE CYPHER
# --------------------------------------------------

if generate:

    if question.strip() == "":

        st.warning("Please enter a question.")

    else:

        start_time = time.time()

        with st.spinner("Generating Cypher Query..."):

            raw_output = generate_cypher_cached(
                question,
                preset,
                limit_instruction,
                model_name,
                temperature,
                schema_section
            )

            cypher = clean_cypher(raw_output)

        end_time = time.time()

        response_time = round(end_time - start_time, 2)

        st.session_state.history.append(question)

        st.divider()

        st.subheader("Generated Cypher Query")

        st.code(cypher, language="cypher")

        st.success(
            f"Query generated successfully in {response_time} seconds."
        )

        st.divider()

        # ------------------------------------------
        # QUERY STATISTICS
        # ------------------------------------------

        stat_col1, stat_col2, stat_col3 = st.columns(3)

        with stat_col1:
            st.metric("Characters", len(cypher))

        with stat_col2:
            st.metric("Words", len(cypher.split()))

        with stat_col3:
            st.metric("Lines", len(cypher.splitlines()))

        st.divider()

        # ------------------------------------------
        # DOWNLOAD BUTTON
        # ------------------------------------------

        st.download_button(
            label="Download Cypher Query",
            data=cypher,
            file_name="generated_query.cypher",
            mime="text/plain",
            use_container_width=True
        )

        # --------------------------------------------------
        # OUTPUT TOOLS
        # --------------------------------------------------

        left, right = st.columns(2)

        with left:
            st.text_area(
                "Copy Cypher Query",
                value=cypher,
                height=150
            )

        with right:
            st.info("""
Tips

• Verify labels before execution

• Check relationship names

• Review generated query

• Modify if required

• Execute inside Neo4j Browser
""")

        st.divider()

        # --------------------------------------------------
        # RAW MODEL OUTPUT
        # --------------------------------------------------

        with st.expander("View Raw Model Output"):
            st.code(raw_output, language="text")

        st.divider()

        # --------------------------------------------------
        # SAMPLE CYPHER
        # --------------------------------------------------

        with st.expander("Cypher Syntax Examples"):
            st.code("""

MATCH (p:Person)
RETURN p

------------------------------------

MATCH (p:Person)
WHERE p.age > 25
RETURN p

------------------------------------

MATCH (p:Person)-[:WORKS_AT]->(c:Company)
RETURN p.name,c.name

------------------------------------

MATCH (c:Company)
RETURN c

------------------------------------

MATCH (p:Person)
RETURN p
LIMIT 10

            """, language="cypher")

# --------------------------------------------------
# SESSION SUMMARY
# --------------------------------------------------

st.divider()

summary_col1, summary_col2, summary_col3 = st.columns(3)

with summary_col1:
    st.info(f"""
Current Model

{model_name}
""")

with summary_col2:
    st.info(f"""
Temperature

{temperature}
""")

with summary_col3:
    st.info(f"""
History

{len(st.session_state.history)} Queries
""")

# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()

st.markdown("""
<div class="footer">

<h3 class="footer-name">
Darshan Patil
</h3>

<p class="footer-role">
AI Engineer • Artificial Intelligence & Data Science
</p>

<p class="footer-note">
Built with Intelligence and Streamlit • LangChain • Ollama • Cypher
</p>
            
<p class="footer-note">
Stay tuned for Neo4j Certificate!
</p>


</div>
""", unsafe_allow_html=True)
