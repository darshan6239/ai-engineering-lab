# 🤖 AI Resume Screener

An AI-powered Resume Screening application built with **Python**, **Streamlit**, and **Groq LLM** that automates candidate evaluation by matching resumes against job descriptions.

The application extracts skills, analyzes candidate profiles, generates a match score, highlights strengths and missing skills, and provides an AI-powered hiring recommendation.

---

## 🚀 Features

- 🔐 Recruiter Login
- 📄 Upload Resume (PDF/DOCX)
- 📝 Paste Job Description
- 🤖 AI-powered Resume Analysis using **Groq LLM**
- 🎯 Resume-to-JD Match Score
- 💡 Hiring Recommendation
- ✅ Key Strength Identification
- ❌ Missing Skill Detection
- 📊 Analytics Dashboard
- 🗂 Candidate History
- ⚙️ Recruiter Settings

---

## 🛠 Tech Stack

- Python
- Streamlit
- Groq API (LLM)
- PDFPlumber
- python-docx
- Pandas
- Matplotlib
- SQLite
- HTML & CSS

---

# 📸 Application Walkthrough

## 1️⃣ Recruiter Login

Recruiters securely log in before accessing the screening dashboard.

<img width="1866" height="841" alt="Screenshot 2026-07-07 023942" src="https://github.com/user-attachments/assets/436c693c-38ad-4fc7-b2dd-58bc843feba0" />

---

## 2️⃣ Dashboard

The main dashboard allows recruiters to:

- Upload a Resume (PDF/DOCX)
- Paste the Job Description
- Navigate between Screen, Descriptions, Analytics, and Settings

Click **Analyze Match** to begin AI evaluation.

<img width="1836" height="772" alt="image" src="https://github.com/user-attachments/assets/f1d9292e-68b6-4733-87ec-ee811b19e735" />

---

## 3️⃣ AI Resume Analysis

Once submitted, the application sends the resume and job description to the **Groq Large Language Model**.

The AI returns:

- Match Score
- Hiring Recommendation
- Reasoning
- Candidate Strengths
- Missing Skills

<img width="1775" height="783" alt="image" src="https://github.com/user-attachments/assets/e311f8d6-6b3c-4feb-b0bf-2794460a2681" />

---

## 4️⃣ Analytics Dashboard

The Analytics page provides:

- Number of candidates screened
- Average match score
- Match score visualization
- Candidate screening history

<img width="1744" height="891" alt="image" src="https://github.com/user-attachments/assets/3528ee7f-855e-4b12-9255-cb9e04b65b42" />

---

## 5️⃣ Settings

Recruiters can:

- Update profile information
- Change organization details
- Manage application settings
- Clear screening history

<img width="1795" height="883" alt="image" src="https://github.com/user-attachments/assets/c434e5e6-5881-400b-906d-8ab76d976bf0" />

---

# 🤖 How Groq is Used

This project integrates the **Groq API** to perform intelligent resume analysis.

The Groq LLM is responsible for:

- Understanding resumes
- Comparing resumes with job descriptions
- Identifying technical skills
- Detecting missing requirements
- Providing recruiter-friendly reasoning
- Generating hiring recommendations

This enables fast and context-aware AI screening instead of relying solely on keyword matching.

---

# 📂 Project Structure

```
AI_Resume_Screener/
│
├── app.py
├── database.py
├── requirements.txt
├── assets/
├── images/
│   ├── login.png
│   ├── dashboard.png
│   ├── analysis.png
│   ├── analytics.png
│   └── settings.png
└── README.md
```

---

# ⚙️ Installation

Clone the repository

```bash
git clone https://github.com/your-username/AI_Resume_Screener.git
```

Move into the project

```bash
cd AI_Resume_Screener
```

Install dependencies

```bash
pip install -r requirements.txt
```

Create a `.env` file

```env
GROQ_API_KEY=your_api_key
```

Run the application

```bash
streamlit run app.py
```

---

# 📈 Future Improvements

- Multi-resume screening
- Resume ranking
- Candidate comparison
- AI-generated interview questions
- Export reports (PDF/Excel)
- Recruiter authentication with database
- Email notifications

---

# 👨‍💻 Author

**Darshan Patil**

GitHub: https://github.com/darshan6239

LinkedIn: https://linkedin.com/in/darshan](https://www.linkedin.com/in/darshanpatil8633/
