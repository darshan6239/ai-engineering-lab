"""
AI Voice & Text Chatbot
-----------------------
An interactive chatbot UI built with Streamlit that can talk to either:
  - Groq API (cloud-hosted LLMs, e.g. Llama 3.3, Mixtral, Gemma2)
  - Ollama (locally-hosted models, e.g. llama3, mistral, phi3)

Features:
  - Keyboard (typed) input
  - Voice input (record in-browser, transcribed to text)
  - Recognized speech is shown to the user BEFORE it is sent to the model
  - Full chat history so the user can ask multiple questions in a row
  - A clear "Exit" control to gracefully end the session
  - Defensive error handling for microphone issues, bad/missing audio,
    network failures, and API errors (auth, rate limit, timeouts, etc.)

Run with:
    streamlit run app.py

NOTE: This file's backend logic (Groq/Ollama calls, session state, voice
transcription, chat flow, error handling) is untouched from the original.
Only the visual layer (CSS/HTML) has been redesigned.
"""

import hashlib
import io

import requests
import streamlit as st

# SpeechRecognition is optional -- the app should still work (text-only)
# if it isn't installed, rather than crashing.
try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False


# --------------------------------------------------------------------------
# Page configuration
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Voice & Text Chatbot",
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------
# PREMIUM UI THEME — CSS + subtle JS
# (Pure presentation layer. No functional/backend code lives here.)
# --------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.cdnfonts.com/css/founders-grotesk');

    :root {
        --bg: #050816;
        --card: rgba(255,255,255,0.04);
        --card-hover: rgba(255,255,255,0.07);
        --border: rgba(255,255,255,0.08);
        --border-strong: rgba(255,255,255,0.16);
        --text: #F5F6FA;
        --text-muted: #A0A3B1;
        --text-faint: #6B6E7B;
        --grad1: #6C63FF;
        --grad2: #7B61FF;
        --grad3: #A855F7;
        --grad4: #00E5FF;
        --success: #00C853;
        --danger: #FF5252;
        --radius: 18px;
    }

    html, body, [class*="css"] {
        font-family: 'Founders Grotesk', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: var(--text);
    }

    /* ---------- App background: simple static gradient (no fixed
       overlays, no z-index tricks — those could sit on top of and hide
       the real UI on some browsers, which is what was happening) ---------- */
    .stApp {
        background:
            radial-gradient(circle at 15% 20%, rgba(108,99,255,0.14), transparent 40%),
            radial-gradient(circle at 85% 15%, rgba(168,85,247,0.11), transparent 45%),
            radial-gradient(circle at 50% 90%, rgba(0,229,255,0.07), transparent 45%),
            var(--bg);
    }

    .main .block-container {
        max-width: 820px;
        padding-top: 2rem;
        padding-bottom: 8rem;
    }

    /* ---------- Header / Logo ---------- */
    @keyframes fadeSlideUp {
        from { opacity: 0; transform: translateY(18px); filter: blur(6px); }
        to   { opacity: 1; transform: translateY(0); filter: blur(0); }
    }
    @keyframes scaleIn {
        from { opacity: 0; transform: scale(0.85); }
        to   { opacity: 1; transform: scale(1); }
    }
    @keyframes gradientShift {
        0%   { background-position: 0% 50%; }
        50%  { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    .app-header {
        text-align: center;
        margin-bottom: 1.6rem;
        animation: fadeSlideUp 0.8s cubic-bezier(0.16,1,0.3,1) both;
    }

    .main-title {
        background: linear-gradient(90deg, var(--grad1), var(--grad2), var(--grad3), var(--grad4));
        background-size: 300% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.6rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin-bottom: 4px;
        animation: gradientShift 8s ease infinite;
    }

    .subtitle {
        color: var(--text-muted);
        font-size: 0.98rem;
        margin-top: 0;
        margin-bottom: 14px;
        font-weight: 400;
    }

    /* ---------- Status pills ---------- */
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 14px 5px 10px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        border: 1px solid var(--border);
        backdrop-filter: blur(12px);
        animation: fadeSlideUp 0.8s 0.15s cubic-bezier(0.16,1,0.3,1) both;
    }
    .status-dot {
        width: 7px; height: 7px; border-radius: 50%;
        display: inline-block;
        animation: breathe 2s ease-in-out infinite;
    }
    @keyframes breathe {
        0%, 100% { opacity: 1; box-shadow: 0 0 0 0 currentColor; }
        50% { opacity: 0.55; box-shadow: 0 0 8px 2px currentColor; }
    }
    .pill-groq { background: rgba(108,99,255,0.10); color: #B5AEFF; }
    .pill-groq .status-dot { background: var(--grad1); color: var(--grad1); }
    .pill-ollama { background: rgba(0,229,255,0.08); color: #7FE9FF; }
    .pill-ollama .status-dot { background: var(--grad4); color: var(--grad4); }

    /* ---------- Section headers ---------- */
    .section-label {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--text-faint);
        margin: 28px 0 10px 2px;
        display: flex;
        align-items: center;
        gap: 8px;
        animation: fadeSlideUp 0.6s both;
    }
    .section-label::after {
        content: "";
        flex: 1;
        height: 1px;
        background: linear-gradient(90deg, var(--border-strong), transparent);
    }

    /* ---------- Glass panel wrapper for widget groups ---------- */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        animation: fadeSlideUp 0.6s cubic-bezier(0.16,1,0.3,1) both;
    }

    /* Streamlit "container" / bordered blocks -> glass cards */
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        backdrop-filter: blur(18px) saturate(160%);
        box-shadow: 0 8px 32px rgba(0,0,0,0.28);
        transition: all 0.35s cubic-bezier(0.16,1,0.3,1);
    }

    /* ---------- Chat messages ---------- */
    @keyframes bubbleIn {
        from { opacity: 0; transform: translateY(14px) scale(0.98); }
        to   { opacity: 1; transform: translateY(0) scale(1); }
    }

    div[data-testid="stChatMessage"] {
        border-radius: 20px !important;
        padding: 14px 18px !important;
        margin-bottom: 10px;
        border: 1px solid var(--border);
        backdrop-filter: blur(14px);
        animation: bubbleIn 0.5s cubic-bezier(0.16,1,0.3,1) both;
        transition: transform 0.25s ease, box-shadow 0.25s ease;
    }
    div[data-testid="stChatMessage"]:hover {
        transform: translateY(-1px);
    }

    /* Single reliable glass style for all chat bubbles (works across
       browsers — no reliance on :has() or fragile position tricks).
       Role is still clear from the avatar icon + name Streamlit renders. */
    div[data-testid="stChatMessage"] {
        background: rgba(255,255,255,0.045);
        border: 1px solid var(--border);
        margin-right: 3%;
    }

    div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li {
        color: var(--text);
        font-size: 0.96rem;
        line-height: 1.55;
    }

    div[data-testid="stChatMessage"] code {
        background: rgba(0,0,0,0.4);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 1px 6px;
        color: #7FE9FF;
    }
    div[data-testid="stChatMessage"] pre {
        background: rgba(0,0,0,0.45) !important;
        border: 1px solid var(--border);
        border-radius: 12px !important;
        padding: 14px !important;
    }

    /* ---------- Buttons ---------- */
    .stButton > button, .stFormSubmitButton > button {
        background: linear-gradient(135deg, var(--grad1), var(--grad2));
        color: #fff;
        border: 1px solid rgba(255,255,255,0.14);
        border-radius: 12px;
        font-weight: 600;
        padding: 0.55em 1.1em;
        box-shadow: 0 4px 18px rgba(108,99,255,0.28);
        transition: all 0.28s cubic-bezier(0.16,1,0.3,1);
        position: relative;
        overflow: hidden;
    }
    .stButton > button:hover, .stFormSubmitButton > button:hover {
        transform: translateY(-2px) scale(1.015);
        box-shadow: 0 8px 28px rgba(123,97,255,0.45);
        border-color: rgba(255,255,255,0.28);
    }
    .stButton > button:active, .stFormSubmitButton > button:active {
        transform: translateY(0) scale(0.98);
    }

    /* secondary buttons (sidebar clear/exit) get a quieter glass look */
    section[data-testid="stSidebar"] .stButton > button {
        background: rgba(255,255,255,0.05);
        color: var(--text);
        box-shadow: none;
        border: 1px solid var(--border);
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.09);
        border-color: var(--border-strong);
        box-shadow: 0 0 0 1px rgba(168,85,247,0.25), 0 6px 20px rgba(0,0,0,0.3);
    }

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {
        background: rgba(8,10,24,0.85);
        backdrop-filter: blur(24px) saturate(160%);
        border-right: 1px solid var(--border);
        animation: fadeSlideUp 0.5s cubic-bezier(0.16,1,0.3,1) both;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        background: linear-gradient(90deg, var(--grad1), var(--grad4));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        letter-spacing: -0.02em;
    }

    /* radio / select styling */
    section[data-testid="stSidebar"] div[role="radiogroup"] label {
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 6px 10px;
        margin-bottom: 4px;
        background: rgba(255,255,255,0.02);
        transition: all 0.2s ease;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background: rgba(255,255,255,0.06);
        border-color: var(--border-strong);
    }

    hr, div[data-testid="stDivider"] {
        border-color: var(--border) !important;
        margin: 18px 0 !important;
    }

    /* ---------- Inputs ---------- */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
        background: rgba(255,255,255,0.035) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        color: var(--text) !important;
        transition: all 0.25s ease;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: rgba(123,97,255,0.6) !important;
        box-shadow: 0 0 0 3px rgba(123,97,255,0.18) !important;
    }
    ::placeholder { color: var(--text-faint) !important; }

    /* chat input pinned at bottom, glassy */
    div[data-testid="stChatInput"] {
        background: rgba(10,12,28,0.75);
        backdrop-filter: blur(22px) saturate(160%);
        border: 1px solid var(--border-strong);
        border-radius: 18px;
        box-shadow: 0 -8px 32px rgba(0,0,0,0.35);
        transition: box-shadow 0.3s ease, border-color 0.3s ease;
    }
    div[data-testid="stChatInput"]:focus-within {
        border-color: rgba(123,97,255,0.55);
        box-shadow: 0 0 0 3px rgba(123,97,255,0.16), 0 -8px 32px rgba(0,0,0,0.35);
    }

    /* audio input widget — compact pill instead of a tall card */
    div[data-testid="stAudioInput"] {
        background: rgba(255,255,255,0.045);
        border: 1px solid var(--border);
        border-radius: 999px;
        padding: 4px 10px;
        backdrop-filter: blur(14px);
        max-width: 420px;
    }
    /* hide the verbose built-in label above the recorder */
    div[data-testid="stAudioInput"] label {
        display: none;
    }
    /* shrink the internal recorder bar/waveform row */
    div[data-testid="stAudioInput"] > div {
        min-height: 0 !important;
        padding: 2px 0 !important;
    }

    /* ---------- Alerts (success/warning/error) ---------- */
    div[data-testid="stAlertContainer"] {
        border-radius: 14px !important;
        border: 1px solid var(--border) !important;
        backdrop-filter: blur(14px);
        animation: fadeSlideUp 0.4s cubic-bezier(0.16,1,0.3,1) both;
    }

    /* ---------- Spinner -> premium loader ---------- */
    div[data-testid="stSpinner"] > div {
        border-top-color: var(--grad3) !important;
        border-right-color: var(--grad4) !important;
    }

    /* ---------- Tabs (Type / Speak) ---------- */
    button[data-baseweb="tab"] {
        color: var(--text-muted);
        font-weight: 600;
        border-radius: 10px 10px 0 0;
        transition: all 0.2s ease;
    }
    button[data-baseweb="tab"]:hover {
        color: var(--text);
        background: rgba(255,255,255,0.04);
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #fff;
        background: rgba(123,97,255,0.14);
    }
    div[data-baseweb="tab-highlight"] {
        background: linear-gradient(90deg, var(--grad1), var(--grad4)) !important;
        height: 3px !important;
        border-radius: 3px;
    }
    div[data-baseweb="tab-border"] { background: var(--border) !important; }

    /* slightly brighter muted text for better readability */
    p, span, label, .stCaption, div[data-testid="stCaptionContainer"] {
        color: var(--text);
    }
    div[data-testid="stCaptionContainer"] p {
        color: #B7BAC9 !important;
        font-size: 0.85rem;
    }

    /* scrollbar */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(var(--grad1), var(--grad3));
        border-radius: 8px;
    }
    ::-webkit-scrollbar-track { background: transparent; }

    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.markdown(
    """
    <div class="app-header">
        <p class="main-title">AI Voice &amp; Text Chatbot</p>
        <p class="subtitle">Ask by typing or speaking — powered by Groq API or a local Ollama model</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# Session state initialization  (UNCHANGED)
# --------------------------------------------------------------------------
defaults = {
    "messages": [],              # chat history: [{"role": "user"/"assistant", "content": str}]
    "conversation_active": True, # False once the user chooses to exit
    "last_audio_hash": None,     # fingerprint of the last processed audio clip
    "recognized_text": "",       # last transcribed voice text, editable before sending
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# --------------------------------------------------------------------------
# Backend callers  (UNCHANGED)
# --------------------------------------------------------------------------
def query_groq(api_key: str, model: str, messages: list, timeout: int = 30) -> str:
    """Send the conversation to the Groq chat-completions API and return the reply text."""
    if not api_key:
        raise ValueError("No Groq API key provided. Add it in the sidebar.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages, "temperature": 0.7}

    response = requests.post(url, headers=headers, json=payload, timeout=timeout)

    if response.status_code == 401:
        raise PermissionError("Invalid Groq API key. Please check the key in the sidebar.")
    if response.status_code == 404:
        raise LookupError(f"Model '{model}' was not found on Groq. Try a different model.")
    if response.status_code == 429:
        raise ConnectionRefusedError("Groq rate limit reached. Please wait a moment and try again.")
    response.raise_for_status()

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError("Received an unexpected response format from Groq.") from exc


def query_ollama(base_url: str, model: str, messages: list, timeout: int = 60) -> str:
    """Send the conversation to a local Ollama server and return the reply text."""
    if not base_url:
        raise ValueError("No Ollama server URL provided.")
    if not model:
        raise ValueError("No Ollama model name provided.")

    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {"model": model, "messages": messages, "stream": False}

    response = requests.post(url, json=payload, timeout=timeout)

    if response.status_code == 404:
        raise LookupError(
            f"Model '{model}' is not available on this Ollama server. "
            f"Try `ollama pull {model}` first."
        )
    response.raise_for_status()

    data = response.json()
    try:
        return data["message"]["content"].strip()
    except (KeyError, TypeError) as exc:
        raise RuntimeError("Received an unexpected response format from Ollama.") from exc


def transcribe_audio(audio_bytes: bytes) -> str:
    """Convert recorded voice audio (WAV bytes) into text."""
    recognizer = sr.Recognizer()
    with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
        audio_data = recognizer.record(source)
    return recognizer.recognize_google(audio_data)


# --------------------------------------------------------------------------
# Sidebar: backend configuration & controls  (logic UNCHANGED, styling only)
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("Settings")

    backend = st.radio("AI Backend", ["Groq API (Cloud)", "Ollama (Local)"], index=0)

    groq_api_key = ""
    groq_model = ""
    ollama_url = ""
    ollama_model = ""

    if backend == "Groq API (Cloud)":
        st.markdown(
            '<span class="status-pill pill-groq"><span class="status-dot"></span>Groq Cloud</span>',
            unsafe_allow_html=True,
        )
        groq_api_key = st.text_input("Groq API Key", type="password", help="Get one at console.groq.com")
        groq_model = st.selectbox(
            "Groq Model",
            [
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "mixtral-8x7b-32768",
                "gemma2-9b-it",
            ],
        )
    else:
        st.markdown(
            '<span class="status-pill pill-ollama"><span class="status-dot"></span>Local Ollama</span>',
            unsafe_allow_html=True,
        )
        ollama_url = st.text_input("Ollama Server URL", value="http://localhost:11434")
        ollama_model = st.text_input("Ollama Model Name", value="llama3")

        if st.button("Check connection / list models"):
            try:
                r = requests.get(f"{ollama_url.rstrip('/')}/api/tags", timeout=5)
                r.raise_for_status()
                tags = [m["name"] for m in r.json().get("models", [])]
                if tags:
                    st.success("Connected. Available models: " + ", ".join(tags))
                else:
                    st.warning("Connected, but no models are pulled yet (try `ollama pull llama3`).")
            except requests.exceptions.ConnectionError:
                st.error("Could not reach Ollama. Is `ollama serve` running?")
            except Exception as exc:
                st.error(f"Connection check failed: {exc}")

    st.divider()

    if not SR_AVAILABLE:
        st.warning(
            "Voice input is disabled because the `SpeechRecognition` package "
            "isn't installed. Run `pip install SpeechRecognition` to enable it."
        )

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Clear chat"):
            st.session_state.messages = []
            st.session_state.recognized_text = ""
            st.rerun()
    with col_b:
        if st.button("Exit"):
            st.session_state.conversation_active = False
            st.rerun()


# --------------------------------------------------------------------------
# Handle "exit" state gracefully  (UNCHANGED)
# --------------------------------------------------------------------------
if not st.session_state.conversation_active:
    st.success("Thanks for chatting! The session has ended.")
    st.caption("Refresh the page or click below to start a new conversation.")
    if st.button("Start a new conversation"):
        st.session_state.conversation_active = True
        st.session_state.messages = []
        st.session_state.recognized_text = ""
        st.rerun()
    st.stop()


# --------------------------------------------------------------------------
# Chat history display  (UNCHANGED)
# --------------------------------------------------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# --------------------------------------------------------------------------
# Shared handler: send a question to the selected backend  (UNCHANGED)
# --------------------------------------------------------------------------
def handle_question(question: str) -> None:
    question = (question or "").strip()

    if not question:
        st.warning("⚠️ I didn't catch a question. Please type or speak something first.")
        return

    if question.lower() in {"exit", "quit", "bye", "stop"}:
        st.session_state.conversation_active = False
        st.rerun()
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                if backend == "Groq API (Cloud)":
                    reply = query_groq(groq_api_key, groq_model, st.session_state.messages)
                else:
                    reply = query_ollama(ollama_url, ollama_model, st.session_state.messages)
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
            except ValueError as exc:
                st.error(f"⚠️ Configuration error: {exc}")
            except PermissionError as exc:
                st.error(f"⚠️ Authentication error: {exc}")
            except LookupError as exc:
                st.error(f"⚠️ {exc}")
            except ConnectionRefusedError as exc:
                st.error(f"⚠️ {exc}")
            except requests.exceptions.ConnectionError:
                st.error(
                    "⚠️ Couldn't connect to the AI backend. "
                    "Check your internet connection (Groq) or that Ollama is running locally."
                )
            except requests.exceptions.Timeout:
                st.error("⚠️ The request timed out. Please try again.")
            except requests.exceptions.HTTPError as exc:
                st.error(f"⚠️ The AI service returned an error: {exc}")
            except Exception as exc:  # final safety net — never crash the app
                st.error(f"⚠️ Unexpected error: {exc}")


# --------------------------------------------------------------------------
# Input area — voice and typing grouped into clear tabs so it's obvious
# there are two ways to ask, without both fighting for attention at once.
# (All underlying logic is unchanged; only the layout/grouping is new.)
# --------------------------------------------------------------------------
st.markdown('<p class="section-label">Ask a question</p>', unsafe_allow_html=True)

tab_type, tab_voice = st.tabs(["Type", "Speak"])

with tab_type:
    st.caption("Type your question below and press Enter to send.")
    typed_question = st.chat_input("Type your question here, or type 'exit' to end the chat...")
    if typed_question is not None:
        handle_question(typed_question)

with tab_voice:
    if SR_AVAILABLE:
        audio_value = st.audio_input("Record your question", label_visibility="collapsed")

        if audio_value is not None:
            audio_bytes = audio_value.getvalue()
            audio_hash = hashlib.md5(audio_bytes).hexdigest()

            # Only re-transcribe when a genuinely new recording comes in
            if audio_hash != st.session_state.last_audio_hash:
                st.session_state.last_audio_hash = audio_hash
                with st.spinner("Transcribing..."):
                    try:
                        st.session_state.recognized_text = transcribe_audio(audio_bytes)
                    except sr.UnknownValueError:
                        st.warning("⚠️ Couldn't understand the audio. Please speak clearly and try again.")
                        st.session_state.recognized_text = ""
                    except sr.RequestError as exc:
                        st.error(f"⚠️ Speech recognition service error: {exc}. Check your internet connection.")
                        st.session_state.recognized_text = ""
                    except Exception as exc:
                        st.error(f"⚠️ Microphone/audio error: {exc}")
                        st.session_state.recognized_text = ""

        if st.session_state.recognized_text:
            st.session_state.recognized_text = st.text_area(
                "Recognized speech (edit if needed, then send):",
                value=st.session_state.recognized_text,
                key="recognized_text_box",
                height=80,
            )
            if st.button("Send voice question", use_container_width=True):
                question = st.session_state.recognized_text
                st.session_state.recognized_text = ""
                st.session_state.last_audio_hash = None
                handle_question(question)
    else:
        st.info("Install `SpeechRecognition` to enable voice input: `pip install SpeechRecognition`")
