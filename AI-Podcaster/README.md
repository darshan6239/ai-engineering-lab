# 🎙️ AI Podcaster

Turn any block of text — an article, your notes, or a full script — into a natural-sounding podcast episode, instantly. AI Podcaster combines a local LLM for summarization with the Kokoro text-to-speech engine to generate downloadable, multi-language narrated audio, all wrapped in a polished Streamlit interface.

---

## Features

- **Text-to-Podcast Generation** — Paste any text and convert it into natural-sounding narrated audio in seconds.
- **Optional AI Summarization** — Toggle on-device summarization (via Ollama + `deepseek-r1:8b`) to condense long-form text into a conversational, easy-to-follow script before narration.
- **9 Languages & Voices** — Generate podcasts in American English, British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese, and Mandarin Chinese, each with a dedicated Kokoro voice.
- **Instant Playback & Download** — Listen directly in-browser and download the resulting `.wav` file with one click.
- **Automatic Cleanup** — Previously generated audio files are cleared automatically to keep storage usage minimal.
- **Modern, Animated UI** — A custom-styled Streamlit interface featuring gradient backgrounds, an animated equalizer loading state, and smooth transitions.

---

## Preview

**EMPTY STATE**

<img width="1919" height="894" alt="Screenshot 2026-07-20 002223" src="https://github.com/user-attachments/assets/b0dea956-c7cd-45ad-84c2-cf95f8ebdef2" />

**GENERATED PODCAST**

<img width="1875" height="798" alt="Screenshot 2026-07-20 002442" src="https://github.com/user-attachments/assets/331e414b-3b8e-49bc-b32a-6db601fc9b67" />

---

## 🧠 How It Works

1. **Input** — The user pastes text into the main text area and selects a target language/voice from the sidebar.
2. **(Optional) Summarization** — If enabled, the raw text is passed through a locally running LLM (`deepseek-r1:8b` via Ollama) using a LangChain prompt template. The model's `<think>...</think>` reasoning traces are stripped, leaving only a clean, conversational summary.
3. **Speech Synthesis** — The (summarized or original) text is passed to a `KPipeline` instance from the [Kokoro](https://github.com/hexgrad/kokoro) TTS library, which generates audio in chunks.
4. **Audio Assembly** — Audio chunks are concatenated with NumPy and written to disk as a `.wav` file using `soundfile`.
5. **Playback** — The final audio is rendered in-browser via Streamlit's native audio player, with a one-click download option.

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| UI Framework | [Streamlit](https://streamlit.io/) |
| Text-to-Speech | [Kokoro](https://github.com/hexgrad/kokoro) |
| LLM Orchestration | [LangChain](https://www.langchain.com/) (`langchain-core`, `langchain-ollama`) |
| Local LLM Runtime | [Ollama](https://ollama.com/) running `deepseek-r1:8b` |
| Audio Processing | NumPy, SoundFile |

---

## Prerequisites

- **Python 3.10+**
- **[Ollama](https://ollama.com/download)** installed and running locally
- The `deepseek-r1:8b` model pulled in Ollama:
  ```bash
  ollama pull deepseek-r1:8b
  ```
- (Optional but recommended) A virtual environment tool such as `venv` or `conda`

---

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/<your-username>/ai-podcaster.git
   cd ai-podcaster
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate      # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start Ollama and pull the required model**
   ```bash
   ollama serve
   ollama pull deepseek-r1:8b
   ```

---

## ▶️ Usage

Launch the app with Streamlit:

```bash
streamlit run app.py
```

Then, in the browser tab that opens:

1. Choose a **language** from the sidebar dropdown.
2. (Optional) Toggle **"Summarize before narrating"** if your text is long and you want a condensed script.
3. Paste or type your text into the input box.
4. Click **✨ Generate Podcast**.
5. Once processing completes, **listen** to the result inline or **download** the `.wav` file.

Generated audio files are stored in `ai-podcaster/audios/` and are automatically cleaned up when a new podcast is generated.

---

## Supported Languages & Voices

| Language | Voice Code |
|---|---|
| 🇺🇸 American English | `af_heart` |
| 🇬🇧 British English | `bf_emma` |
| 🇪🇸 Spanish | `ef_dora` |
| 🇫🇷 French | `ff_siwis` |
| 🇮🇳 Hindi | `hf_alpha` |
| 🇮🇹 Italian | `if_sara` |
| 🇯🇵 Japanese | `jf_alpha` |
| 🇧🇷 Brazilian Portuguese | `pf_dora` |
| 🇨🇳 Mandarin Chinese | `zf_xiaobei` |

---

## 📁 Project Structure

```
ai-podcaster/
├── app.py                # Main Streamlit application
├── requirements.txt       # Python dependencies
├── README.md              # Project documentation
└── ai-podcaster/
    └── audios/            # Generated audio output (auto-created, auto-cleaned)
```

---

## ⚙️ Configuration Notes

- **Caching** — Both the Kokoro `KPipeline` and the Ollama LLM client are cached via `@st.cache_resource` to avoid expensive re-initialization on every interaction.
- **Local-first** — Summarization runs entirely on your machine through Ollama; no text is sent to an external API.
- **Storage management** — Only the most recently generated audio file is retained; older files are deleted automatically before a new one is created.

---

## Troubleshooting

| Issue | Possible Fix |
|---|---|
| `ConnectionError` when summarizing | Ensure `ollama serve` is running and `deepseek-r1:8b` has been pulled. |
| No audio generated / empty output | Check that the input text isn't empty and that Kokoro's language/voice pairing is supported. |
| App is slow on first run | The first call initializes the Kokoro pipeline and LLM connection — subsequent runs are cached and faster. |

---

## Roadmap Ideas

- [ ] Support for multi-speaker/dialogue-style podcasts
- [ ] Export to MP3 in addition to WAV
- [ ] Adjustable narration speed and pitch
- [ ] Batch processing for multiple text inputs

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---
- [LangChain](https://www.langchain.com/) for LLM orchestration
- [Streamlit](https://streamlit.io/) for rapid, elegant UI development
