# SmartHire AI — AI-Driven Smart Hiring Platform & Candidate Career Portal

An intelligent, full-stack recruitment copilot and candidate career hub designed to streamline candidate screening, resume intelligence, ATS optimization, and AI mock interviews with voice chat.

---

## 🌟 Key Features

### Recruiter & Talent Acquisition Copilot
- **Multi-Format Resume Ingestion**: Upload resumes in `.pdf`, `.docx`, or `.txt` format via interactive drag-and-drop or batch folder loading.
- **Intelligent NLP Parsing**:
  - Automatically extracts contact info (name, email, phone).
  - Identifies education, degrees, institutions, and dates.
  - Parses work history, job roles, and timelines.
  - Mines comprehensive technical and domain skill taxonomies.
- **Role-Based Authentication & Security**:
  - Secure registration and login powered by JWT (`python-jose`) and `bcrypt` password hashing.
  - Recruiter, HR Manager, Admin, and Candidate roles supported.
  - Protected REST endpoints with Bearer token authentication.
- **Candidate Directory & Search**:
  - Searchable and filterable candidate database.
  - Detailed candidate profile view with skill badges, education history, and experience timeline.
  - One-click export to CSV and Word (`.docx`).
- **Skills Analytics**:
  - Real-time aggregation of candidate skill distributions.
  - Interactive Plotly visualizations (top skills bar chart, donut chart).
  - Summary metric cards for total talent pool insights.
- **Job Matcher & Scoring**:
  - Multi-factor candidate-job match scoring (skills, nice-to-have, experience fit, seniority).
  - Holistic hiring quality engine (completeness, breadth, stability, education).
  - Individual and pool skill gap reports.

### Candidate Career Portal
- **Candidate Authentication & Profile Isolation**:
  - Dedicated candidate registration and login flow (`role="Candidate"`).
  - Strict data isolation ensuring candidates cannot access other candidates' profiles, resumes, or interview sessions.
- **Resume Parsing & Profile Management**:
  - Upload `.pdf`, `.docx`, or `.txt` resumes with automated parsing.
  - Interactive profile editor to review and update contact details, technical skill tags, experience, education, and projects.
- **AI Resume Intelligence & ATS Scoring**:
  - 10-dimension AI resume audit: Executive summary, ATS compatibility score (0-100), core strengths, improvement areas, project impact rating, and actionable recommendations.
  - Target role alignment and skill gap inspection against open job postings.
- **Interactive Practice Questions**:
  - Practice questions across Technical, Behavioral, and Scenario-based categories with Easy, Medium, and Hard difficulty levels.
  - Supports both Open-ended and Multiple-Choice question formats.
  - Voice recording input via browser microphone (`SpeechRecognition`) and text input.
  - Instant constructive AI feedback with 1-10 scoring, strengths, improvement critique, and exemplar STAR model answers.
- **Live AI Mock Interview Room (Voice & Text)**:
  - Interactive simulated interview with conversational turns and adaptive follow-up probing.
  - Real-time speech recognition for spoken candidate responses.
  - Text-to-speech audio synthesis (`pyttsx3` in-memory WAV playback) for interviewer turns.
  - End-of-interview structured evaluation report with overall score (0-100), hiring verdict, and competency breakdown (Technical Depth, Problem Solving, Communication, Culture Fit).
- **Interview History & Performance Reports**:
  - Archival of past mock interviews, transcripts, competency scores, and actionable feedback roadmaps.

---

## 🏗️ Architecture & Tech Stack

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Streamlit Frontend (8501)                       │
│     ├── Recruiter Portal: Search, Analytics, Pipeline, ATS             │
│     └── Candidate Portal: Profile, Resume AI, Practice, Mock Interview │
└───────────────────────────────────▲────────────────────────────────────┘
                                    │ HTTP / REST (Bearer JWT)
┌───────────────────────────────────▼────────────────────────────────────┐
│                         FastAPI Backend (8000)                         │
│     ├── /api/auth/*        (Register, Login, JWT verification)         │
│     ├── /api/candidate/*   (Profile, Resume, Analysis, Practice, Mock) │
│     ├── /api/candidates/*  (Recruiter ATS candidate operations)        │
│     └── /api/jobs/*        (Job postings & skill matching)             │
└───────────────────▲───────────────────────────────────▲────────────────┘
                    │ SQLAlchemy ORM                    │ LLM Client
┌───────────────────▼──────────────┐   ┌────────────────▼────────────────┐
│         SQLite Database          │   │         AI & LLM Services       │
│  (smarthire.db: Users, Jobs,     │   │  (Sarvam AI / Claude Sonnet /   │
│   Candidates, ResumeAnalysis,    │   │   SpeechRecognition / pyttsx3)  │
│   PracticeAnswer, InterviewSess) │   │                                 │
└──────────────────────────────────┘   └─────────────────────────────────┘
```

- **Frontend**: Streamlit, Plotly Express & Graph Objects, Pandas, `audio-recorder-streamlit`
- **Backend**: FastAPI, Uvicorn, Pydantic v2
- **Authentication**: JWT (`python-jose`), `bcrypt` password hashing, role-based authorization
- **Database / ORM**: SQLite (`smarthire.db`), SQLAlchemy 2.0
- **Document Processing & NLP**: PyMuPDF, `python-docx`, spaCy / Regex rule extractors
- **AI & Voice Services**: Sarvam AI (`sarvam-105b`), Anthropic Claude, `SpeechRecognition` (Google Web Speech API), `pyttsx3` in-memory WAV TTS engine

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+ (Python 3.12 recommended)
- Git

### 2. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/Solitaryking-AI/AI-Driven-Smart-Hiring-Platform.git
cd AI-Driven-Smart-Hiring-Platform

# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Running the Application

You can launch both the backend and frontend simultaneously with the launcher script:

```bash
python run.py
```

Alternatively, launch them in separate terminals:

**Terminal 1 (FastAPI Backend):**
```bash
python api.py
```
Backend API will be available at: `http://localhost:8000` (Docs: `http://localhost:8000/docs`)

**Terminal 2 (Streamlit Frontend):**
```bash
streamlit run app.py
```
Frontend Dashboard will open at: `http://localhost:8501`

---

## 📁 Project Structure

```
├── api.py                          # FastAPI backend & REST endpoints (Candidate + Recruiter)
├── app.py                          # Streamlit UI (Recruiter Dashboard & Candidate Portal)
├── auth.py                         # JWT token handling & bcrypt security
├── database.py                     # SQLAlchemy engine, session setup, and auto-migrations
├── file_loader.py                  # PDF, DOCX, and TXT document loaders
├── models.py                       # SQLAlchemy models (User, Job, Candidate, ResumeAnalysis, PracticeAnswer, InterviewSession)
├── parser.py                       # NLP parsing & entity extraction logic
├── schemas.py                      # Pydantic v2 request/response schemas
├── run.py                          # Dual-server startup script
├── requirements.txt                # Project dependencies
├── services/
│   ├── candidate_service.py        # Candidate resume intelligence, practice evaluation, mock interview scoring
│   ├── interview_assistant.py     # AI interview question generation & conversational turns
│   ├── llm_client.py               # Unified LLM client (Sarvam AI & Claude) with connection pooling
│   ├── matching_engine.py          # Multi-factor candidate-job match scoring
│   ├── hiring_score.py             # Holistic hiring quality engine
│   └── skill_gap_analysis.py       # Candidate & pool skill gap analysis
├── tests/
│   ├── test_candidate_portal.py    # Candidate authentication, profile, resume, practice & mock interview tests
│   ├── test_interview_assistant_performance.py # Performance benchmarks
│   ├── test_analytics.py           # Dashboard analytics tests
│   ├── test_hiring_score.py        # Scoring engine tests
│   ├── test_matching_engine.py     # Job matching tests
│   └── test_skill_gap_analysis.py  # Skill gap tests
├── resumes/                        # Sample resumes for testing and demo
└── uploads/                        # Secure local storage for uploaded candidate resumes
```

---

## 🧪 Testing

Run the comprehensive automated test suite (47 tests):

```bash
pytest tests/ -v
```

---

## 📄 License
This project is licensed under the MIT License.
