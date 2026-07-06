import streamlit as st
import fitz
import docx
import json
import os
import datetime
import pandas as pd

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

st.set_page_config(
    page_title="AI Resume Reviewer",
    page_icon="◆",
    layout="wide"
)

# ---------------------------------------------------------
# Minimal line-icon helper (replaces colorful emoji with a
# single consistent, monochrome icon style)
# ---------------------------------------------------------
_ICON_PATHS = {
    "clip": '<path d="M21 12.5V7a4 4 0 0 0-8 0v10a2.5 2.5 0 0 0 5 0V9"/>',
    "doc": '<path d="M14 3v5a1 1 0 0 0 1 1h5"/><path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2Z"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="0.6" fill="currentColor"/>',
    "spark": '<path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.5 2.5 5-5"/>',
    "cross": '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 4-6 8-6s8 2 8 6"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>',
    "chart": '<path d="M4 20h16"/><rect x="6" y="10" width="3" height="7"/><rect x="11" y="6" width="3" height="11"/><rect x="16" y="13" width="3" height="4"/>',
}


def icon(name, size=18):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;">'
        f'{_ICON_PATHS[name]}</svg>'
    )

# ---------------------------------------------------------
# GLASS THEME (fonts + CSS)
# ---------------------------------------------------------
st.markdown(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <style>
    :root {
        --glass-font: 'Inter', -apple-system, sans-serif;
        --glass-bg: rgba(255,255,255,0.06);
        --glass-border: rgba(255,255,255,0.14);
        --glass-accent: #ffffff;
        --text-soft: rgba(255,255,255,0.65);
    }

    html, body, [class*="css"], .stApp, .stApp * {
        font-family: var(--glass-font) !important;
    }

    .stApp {
        background: radial-gradient(circle at 15% 10%, #3a3a40 0%, transparent 45%),
                    radial-gradient(circle at 85% 85%, #34343a 0%, transparent 50%),
                    linear-gradient(160deg, #1c1c20 0%, #121214 100%);
        color: #f2f2f4;
    }

    .main .block-container {
        max-width: 1000px;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* ---- Glass panel/card ----
       Real st.container(border=True) blocks render as this testid, so
       styling it directly (rather than a hand-rolled div class) means
       content actually nests inside instead of collapsing into an
       empty box. ---- */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--glass-bg);
        border: 1px solid var(--glass-border) !important;
        border-radius: 24px !important;
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.35);
    }

    /* ---- Header greeting ---- */
    .greet-row {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 1rem;
        margin-bottom: 1.4rem;
        flex-wrap: wrap;
    }
    .greet-title {
        font-size: 2rem;
        font-weight: 800;
        color: #ffffff;
        margin: 0;
    }
    .greet-sub {
        color: var(--text-soft);
        font-size: 0.95rem;
        margin-top: 0.15rem;
    }
    .time-pill {
        display: flex;
        gap: 0.6rem;
    }
    .time-pill .chip {
        background: var(--glass-bg);
        border: 1px solid var(--glass-border);
        border-radius: 16px;
        padding: 0.5rem 1rem;
        text-align: center;
        min-width: 68px;
        backdrop-filter: blur(18px);
    }
    .time-pill .chip .big { font-size: 1.1rem; font-weight: 700; color: #fff; }
    .time-pill .chip .small { font-size: 0.7rem; color: var(--text-soft); }

    /* ---- Step card header ---- */
    .step-card-title {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 0.9rem;
        font-weight: 600;
        font-size: 1.05rem;
        color: #fff;
    }
    .step-card-title .icon-badge {
        width: 34px;
        height: 34px;
        border-radius: 12px;
        background: rgba(255,255,255,0.1);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.05rem;
    }

    /* ---- Text area (JD box) ---- */
    .stTextArea textarea, .stTextInput input {
        background-color: rgba(255,255,255,0.05) !important;
        color: #f2f2f4 !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 16px !important;
        font-size: 0.98rem !important;
    }
    .stTextArea textarea::placeholder {
        color: rgba(255,255,255,0.4) !important;
    }

    /* ---- Hide Streamlit's native (collapsed) widget label boxes.
       label_visibility="collapsed" still reserves a space that can pick
       up the theme's secondary background color -- since we draw our
       own titles above each card, we hide these entirely. ---- */
    [data-testid="stWidgetLabel"] {
        display: none !important;
    }

    /* ---- File uploader ----
       Fixed: the dropzone's internal instructions block (icon, "Drag
       and drop..." text, "Limit 200MB..." caption, Browse button) needs
       its own flex layout, otherwise setting min-height on the outer
       dropzone alone causes the inner text nodes to stack/overlap
       instead of flowing vertically. ---- */
    [data-testid="stFileUploaderDropzone"] {
        background-color: rgba(255,255,255,0.05) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 16px !important;
        min-height: 160px;
        color: #f2f2f4;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 0.5rem !important;
        padding: 1rem !important;
    }

    [data-testid="stFileUploaderDropzoneInstructions"] {
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
        gap: 0.3rem !important;
        width: 100%;
    }

    [data-testid="stFileUploaderDropzoneInstructions"] svg {
        display: block !important;
        margin: 0 auto !important;
    }

    [data-testid="stFileUploaderDropzoneInstructions"] > div {
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
    }

    [data-testid="stFileUploader"] button,
    [data-testid="stBaseButton-secondary"] {
        background-color: rgba(255,255,255,0.12) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255,255,255,0.3) !important;
        border-radius: 12px !important;
        margin-top: 0.4rem !important;
    }
    [data-testid="stFileUploaderFile"] {
        background-color: rgba(255,255,255,0.08) !important;
        border-radius: 10px !important;
    }

    label, .stMarkdown, .stSubheader, .stText, p, span, div {
        color: #f2f2f4 !important;
    }

    h1, h2, h3 { color: #ffffff !important; }

    /* ---- Primary pill button (Analyze Match, Sign in) ---- */
    button[kind="primary"], button[kind="primaryFormSubmit"] {
        background-color: #ffffff !important;
        color: #16161a !important;
        border: none !important;
        border-radius: 999px !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        padding: 0.65rem 1.5rem !important;
        box-shadow: 0 6px 18px rgba(0,0,0,0.35);
        transition: all 0.15s ease-in-out;
    }
    button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover {
        background-color: #e8e8ea !important;
        transform: translateY(-1px);
    }
    button[kind="primary"] p, button[kind="primaryFormSubmit"] p {
        color: #16161a !important;
        font-weight: 700 !important;
    }

    /* ---- Secondary pill button (Sign out, etc.) ---- */
    button[kind="secondary"] {
        background-color: rgba(255,255,255,0.1) !important;
        color: #fff !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 999px !important;
        box-shadow: none;
    }
    button[kind="secondary"] p { color: #fff !important; }

    /* ---- Result placeholder ---- */
    .result-placeholder {
        border: 1px dashed var(--glass-border);
        border-radius: 20px;
        padding: 1.8rem 1rem;
        text-align: center;
        background: rgba(255,255,255,0.03);
        margin-top: 0.5rem;
    }
    .result-placeholder .headline { font-size: 1.15rem; font-weight: 600; color: #fff; }
    .result-placeholder .sub { font-size: 0.9rem; color: var(--text-soft); margin-top: 0.3rem; }

    /* ---- Metric card ---- */
    div[data-testid="stMetric"] {
        background-color: rgba(255,255,255,0.06);
        border: 1px solid var(--glass-border);
        border-radius: 16px;
        padding: 0.8rem;
    }
    div[data-testid="stMetricValue"] { color: #ffffff !important; font-weight: 800 !important; }

    /* ---- Bottom floating nav (decorative) ---- */
    .float-nav {
        display: flex;
        justify-content: center;
        margin-top: 2rem;
    }
    .float-nav .pill {
        display: flex;
        gap: 14px;
        background: var(--glass-bg);
        border: 1px solid var(--glass-border);
        border-radius: 999px;
        padding: 0.6rem 1.2rem;
        backdrop-filter: blur(18px);
    }
    .float-nav .dot {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: rgba(255,255,255,0.1);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.95rem;
    }
    .float-nav .dot.active { background: #ffffff; color: #16161a; }

    /* ---- Login screen ---- */
    .login-logo {
        width: 54px;
        height: 54px;
        border-radius: 16px;
        background: rgba(255,255,255,0.1);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.6rem;
        margin: 0 auto 1rem auto;
    }
    .login-title { font-size: 1.4rem; font-weight: 800; color: #fff; }
    .login-sub { font-size: 0.9rem; color: var(--text-soft); margin-bottom: 1.4rem; }

    /* ---- Footer ---- */
    .footer {
        margin-top: 2.2rem;
        text-align: center;
        font-size: 0.85rem;
        color: var(--text-soft);
        border-top: 1px solid var(--glass-border);
        padding-top: 1rem;
    }
    .footer a { color: #fff !important; text-decoration: none; margin: 0 8px; font-weight: 600; }
    .footer a:hover { text-decoration: underline; }
    </style>
    """,
    unsafe_allow_html=True
)


# ---------------------------------------------------------
# SESSION STATE / "LOGIN"
# ---------------------------------------------------------
# Streamlit has no built-in user accounts, so this is a lightweight,
# session-only recruiter sign-in: it just personalizes the experience
# with the recruiter's name (and optional company). It is NOT secure
# authentication -- do not use this to gate anything sensitive.
if "recruiter_name" not in st.session_state:
    st.session_state.recruiter_name = None
    st.session_state.recruiter_company = None

if "active_page" not in st.session_state:
    st.session_state.active_page = "screen"
if "saved_jds" not in st.session_state:
    st.session_state.saved_jds = []
if "history" not in st.session_state:
    st.session_state.history = []
if "active_jd_text" not in st.session_state:
    st.session_state.active_jd_text = ""


def render_login():
    _, mid_col, _ = st.columns([1, 1.3, 1])
    with mid_col:
        with st.container(border=True):
            st.markdown(
                f'<div style="text-align:center;">'
                f'<div class="login-logo" style="margin:0 auto 1rem auto;">{icon("user", 26)}</div>'
                f'<div class="login-title">Recruiter Sign-In</div>'
                f'<div class="login-sub">Sign in to start screening candidates against your job descriptions.</div>'
                f'</div>',
                unsafe_allow_html=True
            )

            with st.form("login_form", clear_on_submit=False):
                name = st.text_input("Your name", placeholder="e.g. Luna Carter")
                company = st.text_input("Company (optional)", placeholder="e.g. Northwind Talent")
                submitted = st.form_submit_button("Sign in", use_container_width=True, type="primary")

            if submitted:
                if name.strip():
                    st.session_state.recruiter_name = name.strip()
                    st.session_state.recruiter_company = company.strip()
                    st.rerun()
                else:
                    st.warning("Please enter your name to continue.")


if not st.session_state.recruiter_name:
    render_login()
    st.stop()


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------
now = datetime.datetime.now()

header_l, header_r = st.columns([3, 1])

with header_l:
    st.markdown(
        f'<div class="greet-title">Hello, {st.session_state.recruiter_name}</div>'
        f'<div class="greet-sub">'
        + (f"{st.session_state.recruiter_company} · " if st.session_state.recruiter_company else "")
        + 'All set to screen your next candidate.</div>',
        unsafe_allow_html=True
    )

with header_r:
    # A plain Python-rendered timestamp only updates when Streamlit
    # reruns (i.e. on the next click), so it looks "frozen". This embeds
    # a tiny self-contained JS clock that ticks on its own every second,
    # independent of the Streamlit script lifecycle.
    st.components.v1.html(
        """
        <style>
          body { margin: 0; font-family: 'Inter', -apple-system, sans-serif; }
          .time-pill { display: flex; gap: 0.6rem; justify-content: flex-end; }
          .chip {
              background: rgba(255,255,255,0.06);
              border: 1px solid rgba(255,255,255,0.14);
              border-radius: 16px;
              padding: 0.5rem 1rem;
              text-align: center;
              min-width: 68px;
              backdrop-filter: blur(18px);
          }
          .chip .big { font-size: 1.1rem; font-weight: 700; color: #fff; }
          .chip .small { font-size: 0.7rem; color: rgba(255,255,255,0.65); }
        </style>
        <div class="time-pill">
            <div class="chip">
                <div class="big" id="day"></div>
                <div class="small" id="weekday"></div>
            </div>
            <div class="chip">
                <div class="big" id="time"></div>
                <div class="small" id="ampm"></div>
            </div>
        </div>
        <script>
          function tick() {
            const now = new Date();
            const weekdays = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
            document.getElementById("day").textContent = String(now.getDate()).padStart(2, "0");
            document.getElementById("weekday").textContent = weekdays[now.getDay()];
            let h = now.getHours();
            const ampm = h >= 12 ? "PM" : "AM";
            h = h % 12; if (h === 0) h = 12;
            const m = String(now.getMinutes()).padStart(2, "0");
            document.getElementById("time").textContent = h + ":" + m;
            document.getElementById("ampm").textContent = ampm;
          }
          tick();
          setInterval(tick, 1000);
        </script>
        """,
        height=80,
    )

if st.button("Sign out", key="logout"):
    st.session_state.recruiter_name = None
    st.session_state.recruiter_company = None
    st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------
# NAV BAR (functional — drives st.session_state.active_page)
# ---------------------------------------------------------
NAV_ITEMS = [
    ("screen", "clip", "Screen"),
    ("descriptions", "doc", "Descriptions"),
    ("analytics", "chart", "Analytics"),
    ("settings", "gear", "Settings"),
]

nav_wrap = st.columns([1, 2, 1])[1]
with nav_wrap:
    nav_cols = st.columns(len(NAV_ITEMS))
    for col, (page_key, icon_name, label) in zip(nav_cols, NAV_ITEMS):
        with col:
            is_active = st.session_state.active_page == page_key
            if st.button(
                label,
                key=f"nav_{page_key}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.active_page = page_key
                st.rerun()

st.markdown("<br>", unsafe_allow_html=True)


def extract_pdf(file):
    text = ""
    pdf = fitz.open(stream=file.read(), filetype="pdf")
    for page in pdf:
        text += page.get_text()
    return text


def extract_docx(file):
    document = docx.Document(file)
    text = "\n".join(para.text for para in document.paragraphs)
    return text


def analyze_resume(resume_text, job_description):

    # Guard against empty/scanned resumes (no extractable text)
    if not resume_text or not resume_text.strip():
        resume_text = "[No extractable text found in this resume file.]"

    # Groq/most LLM context windows are token-limited; trim very long
    # resumes so the prompt (and the JD) always fits and nothing gets cut off
    max_resume_chars = 12000
    if len(resume_text) > max_resume_chars:
        resume_text = resume_text[:max_resume_chars] + "\n[... resume truncated for length ...]"

    prompt = f"""
You are a meticulous, evidence-based Technical Recruiter. You NEVER invent
facts. Every judgment must be traceable to text that actually appears in the
resume or the job description below.

JOB DESCRIPTION:
\"\"\"{job_description}\"\"\"

RESUME:
\"\"\"{resume_text}\"\"\"

TASK:
1. Extract the candidate's real name from the resume text. If it truly cannot
   be found, use "Not specified".
2. Compare the resume against the job description line by line: required
   skills, years of experience, tools/technologies, education, and domain
   knowledge.
3. Compute match_score as a single WHOLE NUMBER integer between 0 and 100
   (never a decimal or fraction like 0.9 — use 90, not 0.9). Be precise and
   granular — do NOT default to round numbers like 50, 70, 80, 90, or 100.
   Real matches rarely land on a clean multiple of 10; weigh each matched or
   missing requirement individually so the final score reflects that nuance
   (for example 63, 78, 87, 94, 96 are all valid and expected outputs).
   Base it strictly on overlap between explicit requirements in the JD and
   explicit evidence in the resume — do not guess or round generously.
4. key_strengths: 3-6 concrete skills/experiences from the RESUME that
   directly match something the JD asks for. Quote the specific skill, not a
   generic phrase.
5. missing_critical_skills: requirements stated in the JD that are NOT
   evidenced anywhere in the resume. If nothing important is missing, return
   an empty list.
6. recommendation: one of "Strong Match", "Good Match", "Possible Match", or
   "Not a Match", chosen consistently with match_score
   (80-100 = Strong Match, 60-79 = Good Match, 40-59 = Possible Match,
   0-39 = Not a Match).
7. reasoning: 2-4 sentences justifying the score using specific evidence from
   both documents.

Respond with ONLY a single valid JSON object and nothing else — no markdown
fences, no commentary before or after. Use exactly this schema:

{{
"candidate_name": "",
"match_score": 0,
"key_strengths": [],
"missing_critical_skills": [],
"recommendation": "",
"reasoning": ""
}}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.1,
        max_tokens=1500,
        response_format={"type": "json_object"}
    )

    return response.choices[0].message.content


if st.session_state.active_page == "screen":

    if st.session_state.saved_jds:
        jd_titles = ["— Type / paste a new JD below —"] + [j["title"] for j in st.session_state.saved_jds]
        picked = st.selectbox("Load a saved job description", jd_titles, label_visibility="collapsed")
        if picked != jd_titles[0]:
            match = next(j for j in st.session_state.saved_jds if j["title"] == picked)
            st.session_state.active_jd_text = match["text"]

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.markdown(
                f'<div class="step-card-title"><span class="icon-badge">{icon("clip")}</span> Resume</div>',
                unsafe_allow_html=True
            )
            uploaded_file = st.file_uploader(
                "Upload Resume",
                type=["pdf", "docx"],
                label_visibility="collapsed"
            )
            st.markdown(
                '<div style="text-align:center; font-size:0.8rem; opacity:0.6; margin-top:0.4rem;">'
                'PDF or DOCX, up to 200MB</div>',
                unsafe_allow_html=True
            )

    with col2:
        with st.container(border=True):
            st.markdown(
                f'<div class="step-card-title"><span class="icon-badge">{icon("doc")}</span> Job Description</div>',
                unsafe_allow_html=True
            )
            job_description = st.text_area(
                "Job Description",
                height=140,
                value=st.session_state.active_jd_text,
                placeholder="Paste the JD here — required skills, years of experience, tools, education...",
                label_visibility="collapsed",
                key="jd_textarea",
            )

    st.markdown("<br>", unsafe_allow_html=True)

    center_col = st.columns([1, 1, 1])[1]
    with center_col:
        analyze_clicked = st.button("Analyze Match", use_container_width=True, type="primary")

    # ---------------------------------------------------------
    # RESULTS AREA
    # ---------------------------------------------------------
    if not analyze_clicked:
        st.markdown(
            """
            <div class="result-placeholder">
                <div class="headline">Your candidate report will appear here</div>
                <div class="sub">Every score is backed by evidence from both documents. No guessing.</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:

        if uploaded_file and job_description:

            if uploaded_file.name.endswith(".pdf"):
                resume_text = extract_pdf(uploaded_file)
            else:
                resume_text = extract_docx(uploaded_file)

            with st.spinner("Analyzing Resume..."):
                result = analyze_resume(resume_text, job_description)

            try:
                clean_json = (
                    result.replace("```json", "")
                    .replace("```", "")
                    .strip()
                )

                data = json.loads(clean_json)

                # Normalize match_score to a clean 0-100 integer no matter how
                # the model formatted it (e.g. "85", "85%", 85.0, or a fraction
                # like 0.85 meaning 85%)
                raw_score = data.get("match_score", 0)
                try:
                    score_val = float(str(raw_score).replace("%", "").strip())
                    # A model sometimes returns a 0-1 fraction instead of 0-100
                    if 0 < score_val <= 1:
                        score_val *= 100
                    match_score = int(round(score_val))
                except (ValueError, TypeError):
                    match_score = 0
                match_score = max(0, min(100, match_score))

                st.session_state.history.append({
                    "candidate_name": data.get("candidate_name", "Candidate"),
                    "score": match_score,
                    "recommendation": data.get("recommendation", "Not available"),
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                })

                with st.container(border=True):
                    st.success(f"Analysis Complete for {data.get('candidate_name', 'Candidate')}")

                    m_col1, m_col2 = st.columns([1, 2])

                    with m_col1:
                        st.metric("Match Score", f"{match_score}%")

                    with m_col2:
                        st.markdown(
                            f'<div class="step-card-title">{icon("target")} Recommendation</div>',
                            unsafe_allow_html=True
                        )
                        st.write(data.get("recommendation", "Not available"))

                    st.markdown(
                        f'<div class="step-card-title">{icon("spark")} Reasoning</div>',
                        unsafe_allow_html=True
                    )
                    st.write(data.get("reasoning", "Not available"))

                    s_col1, s_col2 = st.columns(2)

                    with s_col1:
                        st.markdown(
                            f'<div class="step-card-title">{icon("check")} Key Strengths</div>',
                            unsafe_allow_html=True
                        )
                        strengths = data.get("key_strengths", [])
                        if strengths:
                            for item in strengths:
                                st.markdown(
                                    f'<div style="margin-bottom:4px;">{icon("check", 14)} {item}</div>',
                                    unsafe_allow_html=True
                                )
                        else:
                            st.write("No notable strengths identified.")

                    with s_col2:
                        st.markdown(
                            f'<div class="step-card-title">{icon("cross")} Missing Skills</div>',
                            unsafe_allow_html=True
                        )
                        missing = data.get("missing_critical_skills", [])
                        if missing:
                            for item in missing:
                                st.markdown(
                                    f'<div style="margin-bottom:4px;">{icon("cross", 14)} {item}</div>',
                                    unsafe_allow_html=True
                                )
                        else:
                            st.write("No critical gaps identified.")

            except Exception:
                st.error("Failed to Parse Response")
                st.write(result)

        else:
            st.warning("Upload Resume and Paste Job Description")

elif st.session_state.active_page == "descriptions":
    st.markdown(
        f'<div class="step-card-title">{icon("doc")} Saved Job Descriptions</div>',
        unsafe_allow_html=True
    )

    with st.container(border=True):
        with st.form("save_jd_form", clear_on_submit=True):
            jd_title = st.text_input("Title", placeholder="e.g. Senior Backend Engineer")
            jd_text = st.text_area(
                "Description",
                height=140,
                placeholder="Paste a JD here to save it for reuse on the Screen tab..."
            )
            save_clicked = st.form_submit_button("Save Description", type="primary", use_container_width=True)

        if save_clicked:
            if jd_title.strip() and jd_text.strip():
                st.session_state.saved_jds.append({"title": jd_title.strip(), "text": jd_text.strip()})
                st.success("Saved.")
            else:
                st.warning("Add both a title and the description text.")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.session_state.saved_jds:
        for i, jd in enumerate(st.session_state.saved_jds):
            with st.container(border=True):
                jd_col, del_col = st.columns([5, 1])
                with jd_col:
                    st.markdown(f"**{jd['title']}**")
                    preview = jd["text"][:220] + ("…" if len(jd["text"]) > 220 else "")
                    st.caption(preview)
                with del_col:
                    if st.button("Delete", key=f"del_jd_{i}", use_container_width=True):
                        st.session_state.saved_jds.pop(i)
                        st.rerun()
    else:
        st.info("No saved job descriptions yet. Save one above to reuse it on the Screen tab.")

elif st.session_state.active_page == "analytics":
    st.markdown(
        f'<div class="step-card-title">{icon("chart")} Analytics</div>',
        unsafe_allow_html=True
    )

    if st.session_state.history:
        df = pd.DataFrame(st.session_state.history)

        with st.container(border=True):
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                st.metric("Candidates Screened", len(df))
            with m_col2:
                st.metric("Average Match Score", f"{df['score'].mean():.0f}%")

            st.markdown(
                f'<div class="step-card-title">{icon("target")} Match Scores</div>',
                unsafe_allow_html=True
            )
            st.bar_chart(df.set_index("candidate_name")["score"])

        with st.container(border=True):
            st.markdown(
                f'<div class="step-card-title">{icon("clip")} History</div>',
                unsafe_allow_html=True
            )
            st.dataframe(
                df[["candidate_name", "score", "recommendation", "timestamp"]]
                .rename(columns={
                    "candidate_name": "Candidate",
                    "score": "Score",
                    "recommendation": "Recommendation",
                    "timestamp": "Analyzed At",
                }),
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("No candidates analyzed yet. Run an analysis on the Screen tab to see analytics here.")

elif st.session_state.active_page == "settings":
    st.markdown(
        f'<div class="step-card-title">{icon("gear")} Settings</div>',
        unsafe_allow_html=True
    )

    with st.container(border=True):
        with st.form("settings_form"):
            new_name = st.text_input("Your name", value=st.session_state.recruiter_name)
            new_company = st.text_input("Company", value=st.session_state.recruiter_company or "")
            profile_saved = st.form_submit_button("Save Changes", type="primary", use_container_width=True)

        if profile_saved:
            if new_name.strip():
                st.session_state.recruiter_name = new_name.strip()
                st.session_state.recruiter_company = new_company.strip()
                st.success("Profile updated.")
            else:
                st.warning("Name cannot be empty.")

    with st.container(border=True):
        st.markdown(
            f'<div class="step-card-title">{icon("cross")} Session Data</div>',
            unsafe_allow_html=True
        )
        st.write(f"{len(st.session_state.history)} candidate(s) analyzed this session.")
        st.write(f"{len(st.session_state.saved_jds)} saved job description(s).")
        if st.button("Clear Analysis History", use_container_width=True):
            st.session_state.history = []
            st.rerun()

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------
st.markdown(
    """
    <div class="footer">
        Made by <b>Darshan Patil</b> &nbsp;|&nbsp;
        <a href="https://github.com/darshan6239" target="_blank">GitHub</a>
        &nbsp;|&nbsp;
        <a href="https://www.linkedin.com/in/darshanpatil8633/" target="_blank">LinkedIn</a>
    </div>
    """,
    unsafe_allow_html=True
)
