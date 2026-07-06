# 📊 Text-to-SQL App

Upload any CSV file and ask questions about it in plain English. The app converts your question into a SQL query, runs it against the data, and returns the results as a downloadable table — no SQL knowledge required.

---

## 🎥 Demo

<img width="1778" height="779" alt="image" src="https://github.com/user-attachments/assets/e0a98fe4-9662-4af7-bc9a-16c301d4c1b4" />

<img width="1745" height="833" alt="image" src="https://github.com/user-attachments/assets/a7f7352c-64f7-46de-b140-ba91a8cd34e4" />

```
```

---

## ✨ Features

- 📂 Upload any CSV and instantly preview it (rows, columns, missing values)
- 💬 Ask questions in natural language (e.g. *"Show top 10 rows"*, *"List cars which are only petrol"*)
- 🧠 Automatically generates the matching SQL query using a local LLM
- 📈 Displays results in a clean, sortable table
- 📥 Download query results as a CSV
- 🔒 Runs fully locally — no data leaves your machine (uses a local Ollama model)

---

## 🛠️ Tech Stack

| Layer | Tool |
|---|---|
| UI | [Streamlit](https://streamlit.io/) |
| LLM Orchestration | [LangChain](https://www.langchain.com/) |
| Local LLM | [Ollama](https://ollama.com/) running `qwen2.5:1.5b` |
| Data | Pandas + SQLite |

---

## ⚙️ How It Works

1. You upload a CSV — it's loaded into a temporary SQLite table called `data`.
2. Your question, along with the table's schema, is sent to a local LLM via Ollama.
3. The LLM returns a SQL query, which is cleaned and validated.
4. The query runs against the SQLite table using Pandas, and results are shown as a table.
5. You can download the results as a CSV with one click.

---

## ▶️ Setup & Run Locally

### 1. Clone the repo
```bash
git clone https://github.com/darshan6239/ai-engineering-lab.git
cd ai-engineering-lab/text-to-sql-app
```

### 2. Install dependencies
```bash
pip install streamlit pandas langchain-community langchain-ollama langchain-core
```

### 3. Install & run Ollama
Download Ollama from [ollama.com](https://ollama.com/), then pull the model used by this app:
```bash
ollama pull qwen2.5:1.5b
```
Make sure Ollama is running in the background before starting the app.

### 4. Run the app
```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`.

---

## 📁 Project Structure

```
text-to-sql-app/
│
├── app.py          # Main Streamlit application
└── README.md       # You are here
```

---

## 🚧 Limitations

- Query accuracy depends on the local LLM (`qwen2.5:1.5b`) — larger models will generally produce more reliable SQL.
- Currently supports single-table CSV uploads only.
- No authentication or persistence — each upload starts a fresh session.

## Possible Improvements

- Support multiple CSV uploads with joins across tables
- Add a query history / chat-style interface
- Let users pick which local model to use
- Add basic chart generation from query results

---

## About

Part of my [AI Engineering Lab](../) — a collection of practical AI projects built to solve real, everyday problems.

**Darshan Patil** — AI Engineer | Data Analyst | AI & DS Student
[GitHub](https://github.com/darshan6239) · [LinkedIn](https://www.linkedin.com/in/darshanpatil8633/)
