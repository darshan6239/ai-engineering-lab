import streamlit as st
import pandas as pd
import sqlite3

from langchain_community.utilities import SQLDatabase
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------

st.set_page_config(
    page_title="AI CSV Analyst",
    page_icon="📊",
    layout="wide"
)

# --------------------------------------------------
# CUSTOM CSS
# --------------------------------------------------

st.markdown("""
<style>

.stApp {
    background: radial-gradient(circle at top, #10172a 0%, #0b1020 45%, #060816 100%);
}

.hero {
    padding: 2rem;
    border-radius: 20px;
    background: linear-gradient(
        135deg,
        rgba(59,130,246,0.20),
        rgba(168,85,247,0.20)
    );
    border: 1px solid rgba(255,255,255,0.10);
    margin-bottom: 20px;
}

.hero h1 {
    color: white;
}

.hero p {
    color: #cbd5e1;
}

.footer {
    text-align: center;
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid rgba(255,255,255,0.10);
}

.footer-name {
    color: white;
    margin-bottom: 8px;
}

.footer-role {
    color: #cbd5e1;
    font-size: 18px;
    margin-bottom: 25px;
}

.footer-links {
    margin-bottom: 25px;
}

.footer-btn {
    display: inline-block;
    text-decoration: none;
    padding: 12px 28px;
    border-radius: 10px;
    color: white;
    font-weight: 600;
    margin-right: 15px;
    transition: transform 0.15s ease, opacity 0.15s ease;
}

.footer-btn:last-child {
    margin-right: 0;
}

.footer-btn:hover {
    text-decoration: underline;
    transform: translateY(-2px);
    opacity: 0.9;
}

.footer-btn.github {
    background: #24292e;
}

.footer-btn.linkedin {
    background: #0077B5;
}

.footer-note {
    color: #94a3b8;
    font-size: 14px;
}

</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.markdown("""
<div class="hero">
    <h1>📊 AI CSV Analyst</h1>
    <p>
        Upload any CSV file and ask questions in natural language.
        The AI converts your question into SQL and analyzes the data.
    </p>
</div>
""", unsafe_allow_html=True)

# --------------------------------------------------
# FILE UPLOAD
# --------------------------------------------------

uploaded_file = st.file_uploader(
    "📂 Upload CSV File",
    type=["csv"]
)

if uploaded_file is not None:

    try:

        # ------------------------------------------
        # READ CSV
        # ------------------------------------------

        df = pd.read_csv(uploaded_file)

        st.subheader("📄 Dataset Preview")

        st.dataframe(
            df.head(),
            use_container_width=True
        )

        # ------------------------------------------
        # DATASET STATS
        # ------------------------------------------

        col1, col2, col3 = st.columns(3)

        col1.metric("Rows", df.shape[0])
        col2.metric("Columns", df.shape[1])
        col3.metric(
            "Missing Values",
            int(df.isnull().sum().sum())
        )

        # ------------------------------------------
        # CREATE SQLITE DATABASE
        # ------------------------------------------

        conn = sqlite3.connect("uploaded_data.db")

        df.to_sql(
            "data",
            conn,
            if_exists="replace",
            index=False
        )

        conn.close()

        db = SQLDatabase.from_uri(
            "sqlite:///uploaded_data.db"
        )

        # ------------------------------------------
        # OLLAMA MODEL
        # ------------------------------------------

        llm = ChatOllama(
            model="qwen2.5:1.5b",
            temperature=0
        )

        # ------------------------------------------
        # PROMPT
        # ------------------------------------------

        prompt = ChatPromptTemplate.from_template("""
You are an expert SQL analyst.

Generate ONLY valid SQLite SQL.

Rules:
- Return only SQL
- No explanation
- No markdown
- No ```sql
- Use only the schema provided
- Table name is data

Schema:
{schema}

Question:
{question}
""")

        sql_chain = (
            prompt
            | llm
            | StrOutputParser()
        )

        schema = db.get_table_info()

        # ------------------------------------------
        # QUESTION INPUT
        # ------------------------------------------

        st.subheader("💬 Ask a Question")

        question = st.text_input(
            "Example: Show top 10 rows"
        )

        # ------------------------------------------
        # CLEAN SQL
        # ------------------------------------------

        def clean_sql(sql):
            sql = sql.replace("```sql", "")
            sql = sql.replace("```", "")
            sql = sql.strip()
            return sql

        # ------------------------------------------
        # PROCESS QUESTION
        # ------------------------------------------

        if question:

            with st.spinner("Generating SQL..."):

                raw_sql = sql_chain.invoke({
                    "schema": schema,
                    "question": question
                })

                sql_query = clean_sql(raw_sql)

            st.subheader("🧠 Generated SQL")

            st.code(
                sql_query,
                language="sql"
            )

            try:

                # Run the SQL directly so we always get a real
                # DataFrame back instead of db.run()'s stringified output
                query_conn = sqlite3.connect("uploaded_data.db")

                result_df = pd.read_sql_query(
                    sql_query,
                    query_conn
                )

                query_conn.close()

                st.subheader("📈 Results")

                st.dataframe(
                    result_df,
                    use_container_width=True
                )

                csv = result_df.to_csv(
                    index=False
                ).encode("utf-8")

                st.download_button(
                    label="📥 Download Results as CSV",
                    data=csv,
                    file_name="query_results.csv",
                    mime="text/csv"
                )

            except Exception as e:

                st.error(f"SQL Error: {e}")

                st.subheader("Raw Model Output")

                st.code(raw_sql)

    except Exception as e:

        st.error(f"Error reading CSV: {e}")

# --------------------------------------------------
# FOOTER
# --------------------------------------------------
st.divider()

st.markdown("""
<div class="footer">
<h3 class="footer-name">Darshan Patil</h3>
<p class="footer-role">AI Engineer | Data Analyst | AI & DS Student</p>
<div class="footer-links">
<a href="https://github.com/darshan6239" target="_blank" class="footer-btn github">GitHub</a>
<a href="https://www.linkedin.com/in/darshanpatil8633/" target="_blank" class="footer-btn linkedin">LinkedIn</a>
</div>
<p class="footer-note">Built with Streamlit • LangChain • Ollama • Qwen 2.5</p>
</div>
""", unsafe_allow_html=True)
