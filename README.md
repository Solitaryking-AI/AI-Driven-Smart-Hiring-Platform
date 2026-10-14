# SmartHire AI — AI-Driven Smart Hiring Platform & Candidate Career Portal

An intelligent, full-stack recruitment copilot, candidate career hub, and administrative governance control plane designed to streamline candidate screening, ATS pipeline management, resume intelligence, and AI mock interviews with voice chat.

---

## 🌟 Key Features

### Recruiter & Talent Acquisition Copilot
- **Multi-Format Resume Ingestion**: Upload resumes in `.pdf`, `.docx`, or `.txt` format via interactive drag-and-drop or batch folder loading.
- **Intelligent NLP Parsing**:
  - Automatically extracts contact info (name, email, phone).
  - Identifies education, degrees, institutions, and dates.
  - Parses work history, job roles, and timelines.
  - Mines comprehensive technical and domain skill taxonomies.
- **Candidate Recruitment Pipeline**:
  - 6-stage ATS Kanban workflow: *New*, *Shortlisted*, *Interview*, *Offered*, *Hired*, *Rejected*.
  - Bidirectional drag/move controls with real-time stage counters.
  - Dedicated candidate evaluation modal and instant status updates.
- **Candidate Directory & Search**:
  - Searchable and filterable candidate database with skill badges and profile summaries.
  - One-click export to CSV and Word (`.docx`).
- **Skills Analytics & Hiring Quality Engine**:
  - Real-time aggregation of candidate skill distributions and Plotly charts.
  - Multi-factor candidate-job match scoring (skills, nice-to-have, experience fit, seniority).
  - Holistic hiring score engine (completeness, breadth, stability, education).
  - Individual and talent pool skill gap diagnostics.
- **Pure Recruiter Workspace**: Completely separated shell free of administrative clutter and database purge controls.

### Candidate Career Portal
- **Candidate Authentication & Profile Isolation**:
  - Public registration constrained strictly to `Candidate` accounts.
  - Strict data isolation ensuring candidates cannot access other candidates' profiles, resumes, or interview sessions.
- **Resume Parsing & Profile Management**:
  - Upload `.pdf`, `.docx`, or `.txt` resumes with automated parsing.
  - Interactive profile editor for contact details, technical skills, experience, education, and projects.
- **AI Resume Intelligence & ATS Scoring**:
  - 10-dimension AI resume audit: Executive summary, ATS compatibility score (0-100), core strengths, improvement areas, project impact rating, and actionable recommendations.
  - Target role alignment and skill gap inspection against open job postings.
- **Interactive Practice Questions**:
  - Technical, Behavioral, and Scenario-based categories with Easy, Medium, and Hard difficulty levels.
  - Open-ended and Multiple-Choice formats with microphone voice recording input (`SpeechRecognition`).
  - Instant constructive AI feedback with 1-10 scoring, strengths, improvement critique, and exemplar STAR answers.
- **Live AI Mock Interview Room (Voice & Text)**:
  - Interactive conversational interview with real-time speech recognition for candidate turns.
  - Text-to-speech audio synthesis (`pyttsx3` in-memory WAV playback) for interviewer turns.
  - End-of-interview evaluation report with overall score (0-100), hiring verdict, and competency breakdown.
- **Interview History & Performance Reports**:
  - Full archive of past mock interviews, transcripts, competency scores, and actionable roadmaps.

### Platform Administration & System Governance Control Plane (Admin Only)
- **Dedicated Admin Control Plane (`admin_dashboard.py`)**:
  - Distinct Indigo aesthetic and persistent `ADMIN` identity badge.
  - **Platform Administration Only**: The Admin role is strictly separated from hiring workflows. Administrators see aggregate telemetry and metadata only—never candidate resume content, personal details, or recruiter workspace tools.
- **System Command Center**: Real-time health metrics (user counts, open/closed jobs, active candidates, interviews conducted, AI calls last 7 days, database file size, uploads folder size) and interactive Plotly trajectories.
- **User & Access Governance**:
  - Administrative user provisioning with one-time temporary password display.
  - Safe role promotion/demotion and account deactivation requiring a mandatory justification reason and safety confirmation.
  - Self-demotion/deactivation protection and last-active-administrator lock.
  - Password reset generation for existing users.
- **Recruiter Productivity Auditing**: Per-recruiter activity breakdowns (candidates added, jobs posted, interviews handled).
- **Data Health & Governance**:
  - Duplicate candidate detection (by normalized email), empty skill audits, orphan resume files, and missing disk files.
  - Scoped soft purge with mandatory typed safety confirmation (`PURGE <N> RECORDS`) and single-click candidate restoration.
- **Job Oversight**: Cross-organization job status management and recruiter reassignment.
- **Tamper-Evident Audit Logging**: Chronological security audit trail recording all privileged actions with filter controls and one-click CSV export.
- **AI Telemetry & Usage Monitor**: Latency percentiles (p50/p95), error rate tracking, model call breakdowns, daily volume trends, and top consumer analytics.
- **Platform Feature Flags & Maintenance Banner**: Dynamic platform toggles (`registration_open`, `feature_mock_interview`, `feature_voice`, `feature_resume_ai`, `feature_practice`), system-wide maintenance announcement banner broadcasting across dashboards, and one-click SQLite database snapshot download (`/api/admin/backup`).

---

## 🛡️ Role-Based Access Control & Governance

SmartHire AI enforces complete, zero-leakage role separation. Each role operates within its own bounded API subset and UI shell:

| Role | Scope | UI Shell | Allowed Routes | Access Boundaries & Restrictions |
| :--- | :--- | :--- | :--- | :--- |
| **Admin** | Platform Administration Only | Dedicated Admin Control Plane (`admin_dashboard.py`) | `/api/admin/*`, `/api/auth/*` | **Aggregates & metadata only.** Strictly prohibited from accessing recruiter pipelines, candidate resumes, personal candidate data, job creation, or candidate portal tools. |
| **Recruiter** | Talent Acquisition & Hiring Work | Recruiter ATS (`app.py`) | `/api/candidates/*`, `/api/jobs/*`, `/api/pipeline/*`, `/api/analytics/*`, `/api/interview-sessions/*`, `/api/match` | Strictly prohibited from administrative controls, user provisioning, security audit logs, AI telemetry, or candidate portal features. |
| **Candidate** | Personal Career Hub | Candidate Portal (`app.py`) | `/api/candidate/*`, `/api/auth/*` | Strictly isolated to caller's own profile and sessions; prohibited from viewing recruiter candidate pools, matching engines, or admin tools. |

> [!IMPORTANT]
> **Hiring Work Requires a Recruiter Account**:
> All hiring and talent acquisition activities—including creating and managing job postings, uploading candidates to the recruitment pool, advancing applicants through the ATS Kanban pipeline, running semantic matching, and generating interview guides—**strictly require a Recruiter account**. The Administrator role is confined exclusively to platform health and system governance. If an administrator needs to conduct hiring, a dedicated Recruiter account must be used.
>
> For full technical details and route-level authorization mapping, see [docs/permission_matrix.md](docs/permission_matrix.md).

---

## 🏗️ Architecture & Tech Stack

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Streamlit Frontend (8501)                       │
│     ├── Admin Control Plane: Command Center, Access, Governance, Audit │
│     ├── Recruiter ATS: Pipeline, Directory, Analytics, Job Matcher     │
│     └── Candidate Portal: Profile, Resume AI, Practice, Mock Interview │
└───────────────────────────────────▲────────────────────────────────────┘
                                    │ HTTP / REST (Bearer JWT)
┌───────────────────────────────────▼────────────────────────────────────┐
│                         FastAPI Backend (8000)                         │
│     ├── /api/auth/*        (Register, Login, JWT verification)         │
│     ├── /api/admin/*       (Overview, Users, Governance, Audit, Backup)│
│     ├── /api/candidate/*   (Profile, Resume, Analysis, Practice, Mock) │
│     ├── /api/candidates/*  (Recruiter ATS candidate operations)        │
│     ├── /api/jobs/*        (Job postings & skill matching)             │
│     └── /api/settings      (Public platform flags & announcements)     │
└───────────────────▲───────────────────────────────────▲────────────────┘
                    │ SQLAlchemy ORM                    │ LLM Client
┌───────────────────▼──────────────┐   ┌────────────────▼────────────────┐
│         SQLite Database          │   │         AI & LLM Services       │
│  (smarthire.db: Users, Jobs,     │   │  (Sarvam AI / Claude Sonnet /   │
│   Candidates, ResumeAnalysis,    │   │   SpeechRecognition / pyttsx3)  │
│   PracticeAnswer, InterviewSess, │   │                                 │
│   AuditLog, LlmUsage, Settings)  │   │                                 │
└──────────────────────────────────┘   └─────────────────────────────────┘
```

- **Frontend**: Streamlit, Plotly Express & Graph Objects, Pandas, `audio-recorder-streamlit`
- **Backend**: FastAPI, Uvicorn, Pydantic v2
- **Authentication & Security**: JWT (`python-jose`), `bcrypt` password hashing, role-based authorization guards (`Candidate`, `Recruiter`, `Admin`)
- **Database / ORM**: SQLite (`smarthire.db`), SQLAlchemy 2.0 with safe non-destructive migrations
- **Document Processing & NLP**: PyMuPDF, `python-docx`, spaCy / Regex rule extractors
- **AI & Voice Services**: Sarvam AI (`sarvam-105b`), Anthropic Claude, `SpeechRecognition` (Google Web Speech API), `pyttsx3` in-memory WAV TTS engine

---

## ⚙️ Environment Variables

Configure application settings in `.env` (refer to `.env.example`):

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `SARVAM_API_KEY` | Sarvam AI API key for resume parsing and conversational turns | `your_sarvam_api_key_here` |
| `SMARTHIRE_SECRET_KEY` | Secret key used for signing JWT access tokens | `your_secure_secret_key_here` |
| `SARVAM_MODEL` | *(Optional)* Model identifier for Sarvam AI | `sarvam-105b` |
| `ANTHROPIC_API_KEY` | *(Optional)* Alternative LLM provider key for Claude | `your_anthropic_api_key_here` |
| `BOOTSTRAP_ADMIN_EMAIL` | *(Optional)* Initial admin email provisioned on startup if no admin exists | `admin@smarthire.local` |
| `BOOTSTRAP_ADMIN_PASSWORD` | *(Optional)* Initial bootstrap administrator password | `AdminSecurePassword123!` |

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

Launch both backend and frontend simultaneously with the launcher script:

```bash
python run.py
```

Alternatively, launch them in separate terminals:

**Terminal 1 (FastAPI Backend):**
```bash
python api.py
```
Backend API will be available at: `http://localhost:8000` (Swagger Docs: `http://localhost:8000/docs`)

**Terminal 2 (Streamlit Frontend):**
```bash
streamlit run app.py
```
Frontend Dashboard will open at: `http://localhost:8501`

---

## 📁 Project Structure

```
├── admin_dashboard.py              # Dedicated Admin UI (Command Center, Users, Audit, AI, Settings)
├── admin_routes.py                 # FastAPI APIRouter prefix /api/admin/* (Require Admin guards)
├── api.py                          # FastAPI application, public & recruiter endpoints, error handlers
├── app.py                          # Streamlit UI orchestrator (Recruiter ATS & Candidate Portal)
├── auth.py                         # JWT token issuance, verification, and bcrypt hashing
├── database.py                     # SQLAlchemy session, engine, and non-destructive migrations
├── file_loader.py                  # Multi-format document loader (.pdf, .docx, .txt)
├── models.py                       # SQLAlchemy models (User, Candidate, Job, AuditLog, LlmUsage, Settings)
├── parser.py                       # Resume entity extraction and NLP parsing logic
├── schemas.py                      # Pydantic v2 schemas for all requests and responses
├── ui_common.py                    # Shared UI helpers, SVG icon renderer, and Plotly theme styling
├── run.py                          # Multi-process dual-server runner
├── requirements.txt                # Python package dependencies
├── docs/
│   └── permission_matrix.md        # Complete route and UI permission matrix specification
├── services/
│   ├── audit.py                    # Non-blocking, safe audit log event recorder
│   ├── candidate_service.py        # Resume scoring, practice question evaluation, mock room turns
│   ├── hiring_score.py             # Multi-factor hiring quality scoring engine
│   ├── interview_assistant.py      # Conversational interviewer turn generation
│   ├── llm_client.py               # Unified LLM provider client with usage telemetry tracking
│   ├── matching_engine.py          # Candidate-job semantic matching & ranking
│   ├── settings_store.py           # Database-backed platform settings and feature flag store
│   └── skill_gap_analysis.py       # Candidate and cohort skill deficit diagnostics
├── tests/
│   ├── test_admin_dashboard.py     # Admin API security, user governance, purge, restore, audit tests
│   ├── test_analytics.py           # Dashboard analytics & metric aggregation tests
│   ├── test_candidate_portal.py    # Candidate authentication, profile isolation, and mock room tests
│   ├── test_data_layer_phase1.py   # Soft delete, audit logging, telemetry, and settings store tests
│   ├── test_hiring_score.py        # Candidate scoring formula tests
│   ├── test_integrity_and_security.py # RBAC guards, file sanitization, cascading delete safety tests
│   ├── test_interview_assistant_performance.py # Interview turn benchmarks and caching tests
│   ├── test_matching_engine.py     # Skill taxonomy normalization and overlap tests
│   ├── test_phase1_fixes.py        # Startup, concurrency, WAL mode, bcrypt length validation tests
│   ├── test_phase2_fixes.py        # RBAC, match scores, data health, soft delete, activity tests
│   ├── test_phase3_fixes.py        # Deduplication, acronym casing, 5-pillar scores, error formatting tests
│   ├── test_recruitment_pipeline.py# 6-stage ATS pipeline lifecycle and transition tests
│   ├── test_role_isolation.py      # Route matrix, cross-role 403 enforcement, and access_denied audit tests
│   ├── test_role_management.py     # Supported roles, registration role constraints, HR Manager retirement
│   └── test_skill_gap_analysis.py  # Critical and secondary skill gap evaluation tests
├── resumes/                        # Sample resumes for testing and demonstration
└── uploads/                        # Secure local storage directory for candidate resumes
```

---

## 🧪 Testing

Run the full automated pytest test suite (**141 passing tests**):

```bash
pytest tests/ -v
```

---

## 📄 License
This project is licensed under the MIT License.
