"""
Central configuration for the email automation system.

Reads everything from environment variables (via .env) so the rest of the
codebase never has to guess at defaults or duplicate validation logic.
"""
import os
import sys
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    # Identity / Gmail
    my_email: str = _env("MY_EMAIL", "")

    # Groq (hosted) — used for the higher-stakes generation tasks:
    # writing the customer-facing draft and proofreading it.
    groq_api_key: str = _env("GROQ_API_KEY", "")
    groq_model: str = _env("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")

    # Ollama (local) — used for cheap/fast routing tasks: categorization
    # and RAG query construction, plus embeddings for the vector store.
    ollama_base_url: str = _env("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_llm_model: str = _env("OLLAMA_LLM_MODEL", "qwen2.5:1.5b")
    ollama_embed_model: str = _env("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    # Storage
    db_path: str = _env("DB_PATH", "./data/app.db")
    chroma_persist_dir: str = _env("CHROMA_PERSIST_DIR", "db")

    # Behavior tuning
    max_rewrite_trials: int = int(_env("MAX_REWRITE_TRIALS", "3") or 3)
    email_lookback_hours: int = int(_env("EMAIL_LOOKBACK_HOURS", "8") or 8)
    llm_max_retries: int = int(_env("LLM_MAX_RETRIES", "3") or 3)
    llm_retry_base_seconds: float = float(_env("LLM_RETRY_BASE_SECONDS", "2") or 2)


settings = Settings()


def validate_settings(require_gmail: bool = True) -> list[str]:
    """Returns a list of human-readable problems with the current config.
    Empty list means everything looks fine. Never raises — callers decide
    whether missing config is fatal for their use case."""
    problems = []
    if require_gmail and not settings.my_email:
        problems.append("MY_EMAIL is not set — the agent won't know which inbox is its own.")
    if not settings.groq_api_key:
        problems.append(
            "GROQ_API_KEY is not set — email writing/proofreading will fail. "
            "Get one at https://console.groq.com/keys"
        )
    return problems


def check_ollama_reachable() -> tuple[bool, str]:
    """Best-effort check that Ollama is up and has the models we need pulled.
    Returns (ok, message)."""
    try:
        import httpx
        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3.0)
        resp.raise_for_status()
        installed = {m["name"] for m in resp.json().get("models", [])}
        missing = [
            m for m in (settings.ollama_llm_model, settings.ollama_embed_model)
            if m not in installed and not any(i.startswith(m.split(":")[0]) for i in installed)
        ]
        if missing:
            return False, (
                f"Ollama is running but missing model(s): {', '.join(missing)}. "
                f"Pull them with: " + " && ".join(f"ollama pull {m}" for m in missing)
            )
        return True, "Ollama reachable and models present."
    except Exception as e:
        return False, (
            f"Could not reach Ollama at {settings.ollama_base_url} ({e}). "
            "Is it running? Try: `ollama serve`"
        )


def print_startup_report(require_gmail: bool = True):
    """Prints a clear, actionable summary of config problems at startup
    instead of letting the process crash deep inside a LangChain call."""
    problems = validate_settings(require_gmail=require_gmail)
    ok, ollama_msg = check_ollama_reachable()
    if not ok:
        problems.append(ollama_msg)

    if problems:
        print("⚠️  Startup check found issues:", file=sys.stderr)
        for p in problems:
            print(f"   - {p}", file=sys.stderr)
        print(file=sys.stderr)
    return problems
