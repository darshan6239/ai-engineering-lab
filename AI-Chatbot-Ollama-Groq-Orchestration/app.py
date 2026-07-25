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


# Page configuration & styling
st.set_page_config(
    page_title="AI Voice & Text Chatbot",
    page_icon="",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-title {
        background: linear-gradient(90deg, #6C5CE7, #00CEC9);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.4rem;
        font-weight: 800;
        margin-bottom: 0;
    }
    .subtitle {
        color: #888;
        margin-top: -8px;
        margin-bottom: 1.2rem;
    }
    .status-pill {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .pill-groq { background: #E8F0FE; color: #1A73E8; }
    .pill-ollama { background: #E6FCF5; color: #0CA678; }
    div[data-testid="stChatMessage"] {
        border-radius: 14px;
        padding: 4px 2px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<p class="main-title">🤖 AI Voice & Text Chatbot</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">Ask by typing or speaking — powered by Groq API or a local Ollama model</p>',
    unsafe_allow_html=True,
)


# Session state initialization
defaults = {
    "messages": [],              
    "conversation_active": True, 
    "last_audio_hash": None,    
    "recognized_text": "",     
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# Backend callers
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
# Sidebar: backend configuration & controls
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("Settings")

    backend = st.radio("AI Backend", ["Groq API (Cloud)", "Ollama (Local)"], index=0)

    groq_api_key = ""
    groq_model = ""
    ollama_url = ""
    ollama_model = ""

    if backend == "Groq API (Cloud)":
        st.markdown('<span class="status-pill pill-groq">Groq Cloud</span>', unsafe_allow_html=True)
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
        st.markdown('<span class="status-pill pill-ollama">Local Ollama</span>', unsafe_allow_html=True)
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


# Handle "exit" state gracefully
if not st.session_state.conversation_active:
    st.success("Thanks for chatting! The session has ended.")
    st.caption("Refresh the page or click below to start a new conversation.")
    if st.button("Start a new conversation"):
        st.session_state.conversation_active = True
        st.session_state.messages = []
        st.session_state.recognized_text = ""
        st.rerun()
    st.stop()


# Chat history display
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# Shared handler: send a question to the selected backend
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


# Voice input
st.subheader("Ask by voice")

if SR_AVAILABLE:
    audio_value = st.audio_input("Record your question, then review the text below")

    if audio_value is not None:
        audio_bytes = audio_value.getvalue()
        audio_hash = hashlib.md5(audio_bytes).hexdigest()

        # Only re-transcribe when a genuinely new recording comes in
        if audio_hash != st.session_state.last_audio_hash:
            st.session_state.last_audio_hash = audio_hash
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
        if st.button("Send voice question"):
            question = st.session_state.recognized_text
            st.session_state.recognized_text = ""
            st.session_state.last_audio_hash = None
            handle_question(question)
else:
    st.caption("Install `SpeechRecognition` to enable voice input.")

# Keyboard (typed) input
st.subheader("Ask by typing")
typed_question = st.chat_input("Type your question here, or type 'exit' to end the chat...")

if typed_question is not None:
    handle_question(typed_question)
