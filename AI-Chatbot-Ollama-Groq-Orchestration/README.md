# 🤖 AI Voice & Text Chatbot (Groq API + Ollama)

An interactive Streamlit chatbot that lets you talk to an LLM by **typing** or by
**speaking**, backed by either the **Groq API** (cloud) or a **local Ollama** model.

## Features
- Clean, interactive chat UI (message bubbles, chat history)
- Keyboard input via a chat box
- Voice input recorded right in the browser (no extra software needed)
- Recognized speech is shown **before** it's sent, and you can edit it
- Switch anytime between Groq (cloud) and Ollama (local) models
- Keep asking questions until you choose to exit ("Exit" button, or typing
  `exit` / `quit` / `bye`)
- Graceful handling of microphone errors, unclear audio, missing API keys,
  network failures, and API errors (auth, rate limits, timeouts, bad models)

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

> Note: voice input uses Streamlit's built-in browser microphone widget
> (`st.audio_input`), so no `pyaudio` install or OS-level microphone
> permissions are required beyond the browser prompting you once.

## 2. Set up your model backend

### Option A — Groq API (cloud)
1. Create a free API key at https://console.groq.com
2. Paste it into the sidebar's "Groq API Key" field when the app is running
   (or set it as an environment variable and adapt the code if you prefer
   not to paste it each time).

### Option B — Ollama (local)
1. Install Ollama: https://ollama.com/download
2. Pull a model, e.g.:
   ```bash
   ollama pull llama3
   ```
3. Start the server (usually starts automatically, or run):
   ```bash
   ollama serve
   ```
4. In the app sidebar, select "Ollama (Local)", keep the default URL
   `http://localhost:11434`, and enter the model name you pulled (e.g. `llama3`).
   Use the "Check connection / list models" button to verify.

## 3. Run the app

```bash
streamlit run app.py
```

This opens the chatbot in your browser (usually `http://localhost:8501`).

## 4. Using the chatbot
- **Type**: use the chat box at the bottom and press Enter.
- **Speak**: click the microphone recorder under "Ask by voice", record your
  question, wait for it to transcribe, review/edit the recognized text, then
  click "Send voice question".
- **Exit**: click "Exit" in the sidebar, or simply type `exit`, `quit`, or `bye`.
- **Clear chat**: click "Clear chat" in the sidebar to start a fresh
  conversation without closing the app.

## Error handling built in
| Situation | What happens |
|---|---|
| Empty / blank question | Warning shown, nothing is sent |
| Unintelligible audio | Warning shown, asks you to re-record |
| No internet during transcription | Clear error message shown |
| Missing/invalid Groq API key | Friendly configuration/auth error |
| Unknown model name | Clear "model not found" message |
| Ollama not running | Message telling you to start `ollama serve` |
| Network/timeout issues | Explicit timeout/connection error, app keeps running |
| Any other unexpected error | Caught by a safety net so the app never crashes |

## Customizing
- Add more Groq models to the `groq_model` dropdown list in `app.py`.
- Adjust the CSS block at the top of `app.py` for a different look and feel.
- Swap `recognize_google` in `transcribe_audio()` for another
  `speech_recognition` backend (e.g. Whisper) if you want fully offline
  transcription.
