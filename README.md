# SmartHire AI — AI-Driven Smart Hiring Platform

An intelligent, full-stack recruitment copilot designed to streamline candidate screening, resume parsing, skill analysis, and job matching.

---

## 🌟 Key Features

- **Multi-Format Resume Ingestion**: Upload resumes in `.pdf`, `.docx`, or `.txt` format via interactive drag-and-drop or batch folder loading.
- **Intelligent NLP Parsing**:
  - Automatically extracts contact info (name, email, phone).
  - Identifies education, degrees, institutions, and dates.
  - Parses work history, job roles, and timelines.
  - Mines comprehensive technical and domain skill taxonomies.
- **Role-Based Authentication & Security**:
  - Secure registration and login powered by JWT (`python-jose`) and `bcrypt` password hashing.
  - Recruiter, HR Manager, and Admin roles supported.
  - Protected REST endpoints with Bearer token authentication.
- **Candidate Directory**:
  - Searchable and filterable candidate database.
  - Detailed candidate profile view with skill badges, education history, and experience timeline.
  - One-click export to CSV and JSON.
- **Skills Analytics**:
  - Real-time aggregation of candidate skill distributions.
  - Interactive Plotly visualizations (top skills bar chart, donut chart).
  - Summary metric cards for total talent pool insights.
- **Job Matcher & Scoring**:
  - Input required job skills to rank candidates by compatibility.
  - Visual match scoring with breakdown of matched and missing skill sets.

---

## 🏗️ Architecture & Tech Stack

```
┌────────────────────────────────────────────────────────┐
│                   Streamlit Frontend                   │
│         (Port 8501: Modern Dark/Purple SaaS UI)        │
└───────────────────────────▲────────────────────────────┘
                            │ HTTP / REST (Bearer JWT)
┌───────────────────────────▼────────────────────────────┐
│                    FastAPI Backend                     │
│         (Port 8000: RESTful API & Swagger Docs)        │
└───────────────────────────▲────────────────────────────┘
                            │ SQLAlchemy ORM
┌───────────────────────────▼────────────────────────────┐
│                    SQLite Database                     │
│         (smarthire.db: Candidates & User Models)       │
└────────────────────────────────────────────────────────┘
```

- **Frontend**: Streamlit, Plotly Express & Graph Objects, Pandas
- **Backend**: FastAPI, Uvicorn, Pydantic v2
- **Authentication**: JWT (`python-jose`), `bcrypt` password hashing
- **Database / ORM**: SQLite, SQLAlchemy 2.0
- **Document Processing & NLP**: PyMuPDF (`fitz`), `python-docx`, spaCy / Regex rule extractors

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
├── api.py              # FastAPI application & REST endpoints
├── app.py              # Streamlit dashboard & UI views
├── auth.py             # JWT token handling & bcrypt security
├── database.py         # SQLAlchemy engine & session setup
├── file_loader.py      # PDF, DOCX, and TXT document loaders
├── models.py           # Database models (User, Candidate)
├── parser.py           # NLP parsing & entity extraction logic
├── schemas.py          # Pydantic request/response schemas
├── run.py              # Dual-server startup script
├── requirements.txt    # Project dependencies
├── resumes/            # Sample resumes for testing and demo
└── uploads/            # Temporary storage for uploaded resumes
```

---

## 📄 License
This project is licensed under the MIT License.
