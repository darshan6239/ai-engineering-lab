import os
import re
import time
import uuid

import numpy as np
import soundfile as sf
import streamlit as st
from kokoro import KPipeline
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

AUDIOS_DIRECTORY = "ai-podcaster/audios/"
os.makedirs(AUDIOS_DIRECTORY, exist_ok=True)

SUPPORTED_LANGUAGES = {
    "🇺🇸 American English": ("a", "af_heart"),
    "🇬🇧 British English": ("b", "bf_emma"),
    "🇪🇸 Spanish": ("e", "ef_dora"),
    "🇫🇷 French": ("f", "ff_siwis"),
    "🇮🇳 Hindi": ("h", "hf_alpha"),
    "🇮🇹 Italian": ("i", "if_sara"),
    "🇯🇵 Japanese": ("j", "jf_alpha"),
    "🇧🇷 Brazilian Portuguese": ("p", "pf_dora"),
    "🇨🇳 Mandarin Chinese": ("z", "zf_xiaobei"),
}

SUMMARY_TEMPLATE = """
Summarize the following text by highlighting the key points.
Maintain a conversational tone and keep the summary easy to follow for a general audience.
Text: {text}
"""

st.set_page_config(page_title="AI Podcaster", page_icon="🎙️", layout="centered")


# ---------- cached resources ----------
@st.cache_resource(show_spinner=False)
def get_pipeline(lang_code: str) -> KPipeline:
    return KPipeline(lang_code=lang_code)


@st.cache_resource(show_spinner=False)
def get_llm() -> ChatOllama:
    return ChatOllama(model="deepseek-r1:8b")


def clean_text(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def summarize_text(text: str) -> str:
    prompt = ChatPromptTemplate.from_template(SUMMARY_TEMPLATE)
    chain = prompt | get_llm()
    summary = chain.invoke({"text": text})
    return clean_text(summary.content)


def generate_audio(pipeline: KPipeline, text: str, voice: str) -> str:
    generator = pipeline(text, voice=voice)
    chunks = [audio for _, _, audio in generator]

    if not chunks:
        raise ValueError("No audio was generated for the given text.")

    full_audio = np.concatenate(chunks, axis=0)
    file_name = f"audio_{uuid.uuid4().hex}.wav"
    sf.write(os.path.join(AUDIOS_DIRECTORY, file_name), full_audio, 24000)
    return file_name


def cleanup_previous_file():
    old_file = st.session_state.get("audio_file")
    if old_file:
        path = os.path.join(AUDIOS_DIRECTORY, old_file)
        if os.path.exists(path):
            os.remove(path)


# ---------- styling ----------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');

    html, body, [class*="css"]  { font-family: 'Poppins', sans-serif; }

    .stApp {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        background-size: 200% 200%;
        animation: gradientShift 12s ease infinite;
    }
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    .hero {
        text-align: center;
        padding: 1.2rem 0 0.4rem 0;
        animation: fadeInDown 0.8s ease;
    }
    .hero h1 {
        font-size: 2.6rem;
        font-weight: 700;
        background: linear-gradient(90deg, #ff6ec4, #7873f5, #4ade80);
        background-size: 300% 300%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: shine 6s ease infinite;
        margin-bottom: 0;
    }
    .hero p {
        color: #cfcfe8;
        font-size: 1rem;
        margin-top: 0.2rem;
    }
    @keyframes shine {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    @keyframes fadeInDown {
        from { opacity: 0; transform: translateY(-16px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* card-like containers */
    div[data-testid="stTextArea"] textarea {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 14px;
        color: #f1f1f8;
        transition: border 0.25s ease, box-shadow 0.25s ease;
    }
    div[data-testid="stTextArea"] textarea:focus {
        border: 1px solid #7873f5;
        box-shadow: 0 0 0 3px rgba(120,115,245,0.25);
    }

    section[data-testid="stSidebar"] {
        background: rgba(15,12,41,0.9);
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    div.stButton > button {
        width: 100%;
        border: none;
        border-radius: 999px;
        padding: 0.7rem 1.4rem;
        font-weight: 600;
        color: white;
        background: linear-gradient(90deg, #ff6ec4, #7873f5);
        background-size: 200% auto;
        transition: transform 0.15s ease, box-shadow 0.15s ease, background-position 0.4s ease;
        box-shadow: 0 4px 14px rgba(120,115,245,0.35);
    }
    div.stButton > button:hover {
        transform: translateY(-2px) scale(1.01);
        background-position: right center;
        box-shadow: 0 8px 22px rgba(255,110,196,0.35);
    }
    div.stButton > button:active {
        transform: translateY(0px) scale(0.99);
    }

    /* equalizer loading animation */
    .eq-wrap {
        display: flex;
        justify-content: center;
        align-items: flex-end;
        gap: 6px;
        height: 46px;
        margin: 0.6rem 0 0.2rem 0;
        animation: fadeIn 0.4s ease;
    }
    .eq-wrap span {
        display: block;
        width: 6px;
        border-radius: 4px;
        background: linear-gradient(180deg, #ff6ec4, #7873f5);
        animation: eq 1.1s ease-in-out infinite;
    }
    .eq-wrap span:nth-child(1) { animation-delay: 0s; }
    .eq-wrap span:nth-child(2) { animation-delay: 0.15s; }
    .eq-wrap span:nth-child(3) { animation-delay: 0.3s; }
    .eq-wrap span:nth-child(4) { animation-delay: 0.45s; }
    .eq-wrap span:nth-child(5) { animation-delay: 0.6s; }
    @keyframes eq {
        0%, 100% { height: 8px; }
        50% { height: 40px; }
    }
    .eq-label {
        text-align: center;
        color: #cfcfe8;
        font-size: 0.9rem;
        margin-top: -0.4rem;
    }

    .result-card {
        margin-top: 1rem;
        padding: 1.2rem;
        border-radius: 16px;
        background: rgba(74, 222, 128, 0.08);
        border: 1px solid rgba(74, 222, 128, 0.35);
        animation: fadeIn 0.6s ease;
    }

    div[data-testid="stAudio"] { animation: fadeIn 0.6s ease; }

    footer, #MainMenu { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


def equalizer(label: str):
    st.markdown(
        f"""
        <div class="eq-wrap">
            <span></span><span></span><span></span><span></span><span></span>
        </div>
        <p class="eq-label">{label}</p>
        """,
        unsafe_allow_html=True,
    )


# ---------- header ----------
st.markdown(
    """
    <div class="hero">
        <h1>🎙️ AI Podcaster</h1>
        <p>Turn any text into a natural-sounding podcast, instantly.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------- sidebar settings ----------
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    language = st.selectbox("Language", list(SUPPORTED_LANGUAGES.keys()), index=0)
    should_summarize = st.toggle("Summarize before narrating", value=False)
    st.caption("Summarization runs the text through a local LLM before narration.")

# ---------- main input ----------
text = st.text_area("What should your podcast say?", height=180, placeholder="Paste an article, notes, or a script...")
char_count = len(text)
st.caption(f"{char_count} characters")

button = st.button("✨ Generate Podcast")

status_area = st.empty()

if button:
    if not text.strip():
        st.warning("Please enter some text first.")
    else:
        lang_code, voice = SUPPORTED_LANGUAGES[language]

        try:
            if should_summarize:
                with status_area.container():
                    equalizer("Summarizing your text...")
                text = summarize_text(text)
                status_area.empty()

            with status_area.container():
                equalizer("Narrating your podcast...")

            pipeline = get_pipeline(lang_code)
            cleanup_previous_file()
            file_name = generate_audio(pipeline, text, voice)
            st.session_state["audio_file"] = file_name
            st.session_state["last_summary"] = text if should_summarize else None

            status_area.empty()
            st.balloons()

        except Exception as e:
            status_area.empty()
            st.error(f"Something went wrong: {e}")

if st.session_state.get("audio_file"):
    st.markdown('<div class="result-card">', unsafe_allow_html=True)
    st.markdown("#### 🎧 Your podcast is ready")

    if st.session_state.get("last_summary"):
        with st.expander("View summary used for narration"):
            st.write(st.session_state["last_summary"])

    audio_path = os.path.join(AUDIOS_DIRECTORY, st.session_state["audio_file"])
    st.audio(audio_path)

    with open(audio_path, "rb") as f:
        st.download_button("⬇️ Download audio", f, file_name="podcast.wav", mime="audio/wav")

    st.markdown("</div>", unsafe_allow_html=True)
