import streamlit as st
import requests
import pandas as pd
import json
import os
from typing import Any, Dict, List, Optional
import plotly.express as px
import plotly.graph_objects as go
from services import hiring_score as hiring_score_engine

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SmartHire AI | Recruitment Platform",
    page_icon="S",
    layout="wide",
)

API_BASE_URL = "http://localhost:8000"

# ---------------------------------------------------------------------------
# CSS — Professional SaaS, dark navy + purple brand identity
# ---------------------------------------------------------------------------
def load_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* ── Reset & base ─────────────────────────────────────────────────── */
    *, *::before, *::after { box-sizing: border-box; }

    html, body, .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: #0f172a !important;
        color: #f1f5f9;
        font-size: 14px;
        line-height: 1.6;
    }

    /* ── Design tokens ────────────────────────────────────────────────── */
    :root {
        --bg:        #0f172a;
        --bg-card:   #1e293b;
        --bg-input:  #0f172a;
        --border:    rgba(255,255,255,0.07);
        --border-md: rgba(255,255,255,0.12);
        --primary:   #4F46E5;
        --primary-h: #4338CA;
        --primary-s: rgba(79,70,229,0.10);
        --text:      #f1f5f9;
        --muted:     #64748b;
        --muted-2:   #94a3b8;
        --success:   #10B981;
        --warning:   #F59E0B;
        --danger:    #F43F5E;
        --radius:    8px;
    }

    /* ── Streamlit chrome overrides ───────────────────────────────────── */
    .stApp                         { background: var(--bg) !important; }
    .stApp > header                { background: transparent !important; border-bottom: 1px solid var(--border); }
    [data-testid="stSidebar"]      { background: #1a2234 !important; border-right: 1px solid var(--border) !important; width: 228px !important; }
    [data-testid="stSidebarNav"]   { display: none; }
    .block-container               { padding: 24px 28px !important; max-width: 1200px; }

    /* ── Typography ───────────────────────────────────────────────────── */
    h1, h2, h3, h4, h5, h6        { color: var(--text) !important; margin: 0; }
    p, span, li, label             { color: var(--text) !important; }

    .sh-page-title {
        font-size: 20px;
        font-weight: 600;
        color: var(--text) !important;
        letter-spacing: -0.3px;
        margin: 0;
        line-height: 1.3;
    }
    .sh-page-subtitle {
        font-size: 13px;
        color: var(--muted) !important;
        margin-top: 2px;
    }
    .sh-section-label {
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted) !important;
        margin: 20px 0 8px;
        padding-left: 2px;
    }
    .sh-section-heading {
        font-size: 15px;
        font-weight: 600;
        color: var(--text) !important;
        margin: 0 0 4px;
    }

    /* ── Cards ────────────────────────────────────────────────────────── */
    .sh-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 16px;
        margin-bottom: 12px;
    }
    .sh-card-sm {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 12px 14px;
    }

    /* ── Stat row ─────────────────────────────────────────────────────── */
    .sh-stats-row {
        display: flex;
        gap: 1px;
        background: var(--border);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        overflow: hidden;
        margin-bottom: 20px;
    }
    .sh-stat-item {
        flex: 1;
        background: var(--bg-card);
        padding: 14px 18px;
    }
    .sh-stat-value {
        font-size: 24px;
        font-weight: 700;
        color: var(--text) !important;
        line-height: 1.2;
    }
    .sh-stat-label {
        font-size: 11px;
        color: var(--muted) !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-top: 2px;
    }

    /* ── Sidebar elements ─────────────────────────────────────────────── */
    .sh-brand {
        padding: 16px 16px 12px;
        border-bottom: 1px solid var(--border);
        margin-bottom: 8px;
    }
    .sh-brand-name {
        font-size: 15px;
        font-weight: 700;
        color: var(--text) !important;
        letter-spacing: -0.2px;
    }
    .sh-brand-sub {
        font-size: 11px;
        color: var(--muted) !important;
        margin-top: 1px;
    }
    .sh-user-block {
        padding: 12px 16px;
        border-top: 1px solid var(--border);
        margin-top: 8px;
    }
    .sh-user-name {
        font-size: 13px;
        font-weight: 600;
        color: var(--text) !important;
    }
    .sh-user-meta {
        font-size: 11px;
        color: var(--muted) !important;
        margin-top: 1px;
    }

    /* ── Buttons ──────────────────────────────────────────────────────── */
    .stButton > button {
        background: var(--primary) !important;
        color: #fff !important;
        border: none !important;
        border-radius: var(--radius) !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 7px 16px !important;
        height: 34px !important;
        line-height: 1 !important;
        transition: background 0.15s ease !important;
        box-shadow: none !important;
        letter-spacing: 0.01em;
    }
    .stButton > button:hover {
        background: var(--primary-h) !important;
        transform: none !important;
        box-shadow: none !important;
    }
    /* Secondary / ghost button — apply via key prefix trick */
    .stButton.sh-btn-secondary > button {
        background: transparent !important;
        border: 1px solid var(--border-md) !important;
        color: var(--muted-2) !important;
    }
    .stButton.sh-btn-secondary > button:hover {
        border-color: var(--primary) !important;
        color: var(--text) !important;
    }
    /* Sidebar nav buttons */
    [data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        border: none !important;
        color: var(--muted-2) !important;
        font-size: 13px !important;
        font-weight: 400 !important;
        padding: 6px 12px !important;
        height: 32px !important;
        text-align: left !important;
        width: 100% !important;
        border-radius: 6px !important;
        justify-content: flex-start !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: var(--primary-s) !important;
        color: var(--text) !important;
    }
    /* Danger button */
    [data-testid="stSidebar"] .stButton > button.sh-danger {
        color: var(--danger) !important;
    }

    /* ── Inputs ───────────────────────────────────────────────────────── */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div,
    .stMultiselect > div > div {
        background: var(--bg-input) !important;
        border: 1px solid var(--border-md) !important;
        border-radius: var(--radius) !important;
        color: var(--text) !important;
        font-size: 13px !important;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 2px rgba(79,70,229,0.15) !important;
    }
    .stTextInput label, .stSelectbox label,
    .stMultiselect label, .stTextArea label,
    .stFileUploader label {
        font-size: 12px !important;
        font-weight: 500 !important;
        color: var(--muted-2) !important;
        margin-bottom: 4px !important;
    }

    /* ── File uploader ────────────────────────────────────────────────── */
    [data-testid="stFileUploader"] {
        background: var(--bg-card) !important;
        border: 1px dashed var(--border-md) !important;
        border-radius: var(--radius) !important;
        padding: 24px !important;
    }
    [data-testid="stFileUploader"] > div {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 6px;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] span {
        font-size: 13px !important;
        color: var(--muted-2) !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] small {
        font-size: 11px !important;
        color: var(--muted) !important;
    }

    /* ── Tabs ─────────────────────────────────────────────────────────── */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        background: transparent !important;
        border-bottom: 1px solid var(--border) !important;
        gap: 0 !important;
        padding: 0 !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab"] {
        font-size: 13px !important;
        font-weight: 500 !important;
        color: var(--muted) !important;
        padding: 8px 16px !important;
        border-bottom: 2px solid transparent !important;
        background: transparent !important;
        border-radius: 0 !important;
        margin-right: 0 !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
        color: var(--primary) !important;
        border-bottom-color: var(--primary) !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] { display: none; }
    [data-testid="stTabs"] [data-baseweb="tab-border"]    { display: none; }

    /* ── Expanders ────────────────────────────────────────────────────── */
    [data-testid="stExpander"] {
        border: 1px solid var(--border) !important;
        border-radius: var(--radius) !important;
        background: var(--bg-card) !important;
        margin-bottom: 6px !important;
    }
    [data-testid="stExpander"] summary {
        background: transparent !important;
        border-radius: var(--radius) !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        color: var(--text) !important;
        padding: 10px 14px !important;
    }
    [data-testid="stExpander"] summary:hover {
        background: var(--primary-s) !important;
    }
    [data-testid="stExpander"] > div:last-child {
        padding: 0 14px 12px !important;
        border-top: 1px solid var(--border) !important;
    }

    /* ── Dataframes ───────────────────────────────────────────────────── */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--border) !important;
        border-radius: var(--radius) !important;
        overflow: hidden;
    }
    .stDataFrame iframe {
        border-radius: var(--radius) !important;
    }

    /* ── Progress bar ─────────────────────────────────────────────────── */
    .stProgress > div > div > div {
        background: var(--primary) !important;
        height: 3px !important;
        border-radius: 99px !important;
    }
    .stProgress > div > div {
        background: rgba(255,255,255,0.06) !important;
        border-radius: 99px !important;
        height: 3px !important;
    }

    /* ── Alerts / info boxes ──────────────────────────────────────────── */
    [data-testid="stAlert"] {
        border-radius: var(--radius) !important;
        font-size: 13px !important;
        border-left-width: 3px !important;
    }

    /* ── Skill badges ─────────────────────────────────────────────────── */
    .sh-badge {
        display: inline-block;
        font-size: 11px;
        font-weight: 500;
        padding: 2px 8px;
        border-radius: 4px;
        margin: 2px 3px 2px 0;
        letter-spacing: 0.01em;
    }
    .sh-badge-primary  { background: rgba(79,70,229,0.18); color: #a5b4fc !important; }
    .sh-badge-success  { background: rgba(16,185,129,0.15); color: #6ee7b7 !important; }
    .sh-badge-danger   { background: rgba(244,63,94,0.15);  color: #fda4af !important; }
    .sh-badge-neutral  { background: rgba(255,255,255,0.06); color: var(--muted-2) !important; }

    /* ── Score badge ──────────────────────────────────────────────────── */
    .sh-score-high   { display:inline-block; font-size:12px; font-weight:700; padding:2px 8px; border-radius:4px; background:rgba(16,185,129,0.15); color:#6ee7b7 !important; }
    .sh-score-mid    { display:inline-block; font-size:12px; font-weight:700; padding:2px 8px; border-radius:4px; background:rgba(245,158,11,0.15); color:#fcd34d !important; }
    .sh-score-low    { display:inline-block; font-size:12px; font-weight:700; padding:2px 8px; border-radius:4px; background:rgba(244,63,94,0.15);  color:#fda4af !important; }

    /* ── Candidate row (custom HTML) ──────────────────────────────────── */
    .sh-cand-row {
        display: flex;
        align-items: center;
        padding: 10px 14px;
        border-bottom: 1px solid var(--border);
        gap: 12px;
        transition: background 0.1s;
    }
    .sh-cand-row:last-child { border-bottom: none; }
    .sh-cand-row:hover { background: var(--primary-s); }
    .sh-cand-name  { font-size: 13px; font-weight: 600; color: var(--text) !important; min-width: 160px; }
    .sh-cand-email { font-size: 12px; color: var(--muted) !important; min-width: 180px; }
    .sh-cand-skills { flex: 1; }
    .sh-cand-source { font-size: 11px; color: var(--muted) !important; min-width: 120px; }

    /* ── Match result row ─────────────────────────────────────────────── */
    .sh-match-row {
        display: flex;
        align-items: flex-start;
        padding: 14px 16px;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        margin-bottom: 8px;
        background: var(--bg-card);
        gap: 16px;
    }
    .sh-match-info { flex: 1; }
    .sh-match-name { font-size: 14px; font-weight: 600; color: var(--text) !important; margin-bottom: 2px; }
    .sh-match-email { font-size: 12px; color: var(--muted) !important; margin-bottom: 6px; }
    .sh-match-subscores { font-size: 11px; color: var(--muted) !important; margin-top: 2px; margin-bottom: 6px; }
    .sh-match-subscores b { color: var(--muted-2) !important; font-weight: 600; }
    .sh-match-score-col { text-align: right; min-width: 60px; }
    .sh-progress-track {
        width: 100%;
        height: 3px;
        background: rgba(255,255,255,0.08);
        border-radius: 99px;
        margin-top: 8px;
        overflow: hidden;
    }
    .sh-progress-fill { height: 3px; border-radius: 99px; }

    /* ── Auth pages ───────────────────────────────────────────────────── */
    .sh-auth-logo {
        font-size: 22px;
        font-weight: 700;
        color: var(--primary) !important;
        letter-spacing: -0.5px;
        margin-bottom: 2px;
    }
    .sh-auth-sub {
        font-size: 13px;
        color: var(--muted) !important;
        margin-bottom: 24px;
    }
    .sh-auth-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 28px 28px 24px;
    }
    .sh-form-heading {
        font-size: 16px;
        font-weight: 600;
        color: var(--text) !important;
        margin-bottom: 16px;
    }
    .sh-divider {
        height: 1px;
        background: var(--border);
        margin: 16px 0;
    }

    /* ── Upload file list ─────────────────────────────────────────────── */
    .sh-file-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 12px;
        border: 1px solid var(--border);
        border-radius: 6px;
        margin-bottom: 6px;
        background: var(--bg-card);
        font-size: 12px;
    }
    .sh-file-name { color: var(--text) !important; font-weight: 500; }
    .sh-file-size { color: var(--muted) !important; }

    /* ── Tables (candidate table header) ─────────────────────────────── */
    .sh-table-header {
        display: flex;
        align-items: center;
        padding: 8px 14px;
        border-bottom: 1px solid var(--border);
        gap: 12px;
        background: var(--bg-card);
        border-radius: 8px 8px 0 0;
    }
    .sh-th {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--muted) !important;
    }
    .sh-th-name  { min-width: 160px; }
    .sh-th-email { min-width: 180px; }
    .sh-th-skills { flex: 1; }
    .sh-th-source { min-width: 120px; }

    /* ── Misc ─────────────────────────────────────────────────────────── */
    .sh-separator { height: 1px; background: var(--border); margin: 16px 0; }
    hr { border: none; border-top: 1px solid var(--border); margin: 16px 0; }
    [data-testid="stSpinner"] { color: var(--primary) !important; }
    .stDownloadButton > button {
        background: transparent !important;
        border: 1px solid var(--border-md) !important;
        color: var(--muted-2) !important;
        font-size: 12px !important;
        padding: 5px 14px !important;
        height: 30px !important;
        border-radius: var(--radius) !important;
    }
    .stDownloadButton > button:hover {
        border-color: var(--primary) !important;
        color: var(--text) !important;
        background: var(--primary-s) !important;
    }
    /* Hide Streamlit branding */
    [data-testid="stDecoration"]   { display: none; }
    footer                         { display: none; }
    #MainMenu                      { display: none; }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# API helper
# ---------------------------------------------------------------------------
def api_request(method: str, endpoint: str, token: str = None, **kwargs):
    url = f"{API_BASE_URL}{endpoint}"
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 401:
            return {"error": "Session expired. Please log in again.", "__unauthorized": True}
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            return {"error": detail}
        try:
            return resp.json()
        except Exception:
            return {"success": True}
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to backend. Make sure the FastAPI server is running on http://localhost:8000"}
    except Exception as e:
        return {"error": str(e)}


def _handle_unauthorized(res: dict):
    if isinstance(res, dict) and res.get("__unauthorized"):
        for key in ("auth_token", "user"):
            st.session_state.pop(key, None)
        st.error("Your session has expired. Please log in again.")
        st.rerun()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ROLES = ["Recruiter", "HR Manager", "Admin"]

def _display_name(name: Any, default: str = "Unknown Candidate") -> str:
    if not name or str(name).strip().lower() in ("none", "null", "nan", ""):
        return default
    return str(name).strip()

def _display_email(email: Any, default: str = "—") -> str:
    if not email or str(email).strip().lower() in ("none", "null", "nan", ""):
        return default
    return str(email).strip()

def _score_badge(score: float) -> str:
    cls = "sh-score-high" if score >= 70 else "sh-score-mid" if score >= 40 else "sh-score-low"
    return f"<span class='{cls}'>{score:.0f}%</span>"

def _hiring_score_badge(score: float) -> str:
    cls = "sh-score-high" if score >= 75 else "sh-score-mid" if score >= 55 else "sh-score-low"
    return f"<span class='{cls}'>HS: {score:.0f}%</span>"

def _score_bar_color(score: float) -> str:
    return "#10B981" if score >= 70 else "#F59E0B" if score >= 40 else "#F43F5E"

def _skill_badges(skills: list, variant: str = "primary", limit: int = 0) -> str:
    shown = skills[:limit] if limit else skills
    badges = "".join(f"<span class='sh-badge sh-badge-{variant}'>{s}</span>" for s in shown)
    if limit and len(skills) > limit:
        badges += f"<span class='sh-badge sh-badge-neutral'>+{len(skills)-limit}</span>"
    return badges

def _fmt_bytes(n: int) -> str:
    return f"{n/1024:.0f} KB" if n >= 1024 else f"{n} B"


# ---------------------------------------------------------------------------
# Auth — Login
# ---------------------------------------------------------------------------
def show_login():
    load_css()
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("<div class='sh-auth-logo'>SmartHire AI</div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-auth-sub'>AI-powered recruitment platform</div>", unsafe_allow_html=True)

        st.markdown("<div class='sh-auth-card'>", unsafe_allow_html=True)
        st.markdown("<div class='sh-form-heading'>Sign in to your account</div>", unsafe_allow_html=True)

        email    = st.text_input("Work Email", placeholder="you@company.com", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        c1, c2 = st.columns([1, 1])
        with c1:
            login_clicked = st.button("Sign In", type="primary", use_container_width=True)
        with c2:
            if st.button("Create account", use_container_width=True):
                st.session_state["auth_page"] = "register"
                st.rerun()

        if login_clicked:
            if not email.strip() or not password:
                st.error("Please fill in all fields.")
            else:
                with st.spinner("Signing in…"):
                    res = api_request("POST", "/api/auth/login",
                                      json={"email": email.strip(), "password": password})
                if "error" in res:
                    st.error(res["error"])
                else:
                    st.session_state["auth_token"] = res["access_token"]
                    st.session_state["user"]       = res["user"]
                    st.session_state.pop("auth_page", None)
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Auth — Register
# ---------------------------------------------------------------------------
def show_register():
    load_css()
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("<div class='sh-auth-logo'>SmartHire AI</div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-auth-sub'>Create your recruiter account</div>", unsafe_allow_html=True)

        st.markdown("<div class='sh-auth-card'>", unsafe_allow_html=True)
        st.markdown("<div class='sh-form-heading'>Create account</div>", unsafe_allow_html=True)

        full_name    = st.text_input("Full Name",     placeholder="Jane Smith",          key="reg_name")
        work_email   = st.text_input("Work Email",    placeholder="jane@company.com",    key="reg_email")

        c1, c2 = st.columns(2)
        with c1:
            company_name = st.text_input("Company", placeholder="Acme Corp",             key="reg_company")
        with c2:
            job_title    = st.selectbox("Role",      ROLES,                              key="reg_role")

        phone        = st.text_input("Phone (optional)", placeholder="+1 555 000 0000",  key="reg_phone")

        c1, c2 = st.columns(2)
        with c1:
            password     = st.text_input("Password",         type="password",            key="reg_pass")
        with c2:
            confirm_pass = st.text_input("Confirm Password", type="password",            key="reg_confirm")

        st.caption("Min 8 characters · at least one letter and one number")

        cb1, cb2 = st.columns([1, 1])
        with cb1:
            reg_clicked = st.button("Create Account", type="primary", use_container_width=True)
        with cb2:
            if st.button("Back to Sign In", use_container_width=True):
                st.session_state["auth_page"] = "login"
                st.rerun()

        if reg_clicked:
            errors = []
            if not full_name.strip():    errors.append("Full name is required.")
            if not work_email.strip():   errors.append("Email is required.")
            if not company_name.strip(): errors.append("Company name is required.")
            if not password:             errors.append("Password is required.")
            if password != confirm_pass: errors.append("Passwords do not match.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                payload = {
                    "full_name":       full_name.strip(),
                    "email":           work_email.strip().lower(),
                    "password":        password,
                    "confirm_password": confirm_pass,
                    "company_name":    company_name.strip(),
                    "job_title":       job_title,
                    "phone_number":    phone.strip() or None,
                }
                with st.spinner("Creating account…"):
                    res = api_request("POST", "/api/auth/register", json=payload)
                if "error" in res:
                    st.error(res["error"])
                else:
                    st.session_state["auth_token"] = res["access_token"]
                    st.session_state["user"]       = res["user"]
                    st.session_state.pop("auth_page", None)
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
def show_dashboard():
    load_css()

    token = st.session_state.get("auth_token")
    user  = st.session_state.get("user", {})

    # ── Sidebar ──────────────────────────────────────────────────────────
    with st.sidebar:
        # Brand
        st.markdown("""
        <div class='sh-brand'>
            <div class='sh-brand-name'>SmartHire AI</div>
            <div class='sh-brand-sub'>Recruitment Platform</div>
        </div>
        """, unsafe_allow_html=True)

        # Quick actions
        st.markdown("<div class='sh-section-label'>Actions</div>", unsafe_allow_html=True)

        if st.button("Parse Demo Resumes", use_container_width=True):
            demo_dir = "resumes"
            if os.path.exists(demo_dir):
                files = [f for f in os.listdir(demo_dir) if f.endswith((".pdf", ".docx", ".txt"))]
                if files:
                    bar = st.progress(0)
                    for i, fn in enumerate(files):
                        fpath = os.path.join(demo_dir, fn)
                        with open(fpath, "rb") as f:
                            res = api_request("POST", "/api/candidates/upload", token=token,
                                              files={"file": (fn, f, "application/octet-stream")})
                        _handle_unauthorized(res)
                        icon = "✓" if "error" not in res else "✗"
                        st.toast(f"{icon} {fn}")
                        bar.progress((i + 1) / len(files))
                    st.success(f"Parsed {len(files)} files.")
                    st.rerun()
                else:
                    st.warning("No files found in resumes/")
            else:
                st.warning("resumes/ directory not found.")

        if st.button("Clear All Candidates", use_container_width=True):
            res = api_request("DELETE", "/api/candidates", token=token)
            _handle_unauthorized(res)
            if "error" in res:
                st.error(res["error"])
            else:
                st.success(f"Cleared {res.get('deleted', 0)} candidates.")
                st.rerun()

        # Spacer — push user block to bottom
        st.markdown("<div style='flex:1;'></div>", unsafe_allow_html=True)
        st.markdown("<br>" * 6, unsafe_allow_html=True)

        # User block
        st.markdown(f"""
        <div class='sh-user-block'>
            <div class='sh-user-name'>{user.get('full_name', 'User')}</div>
            <div class='sh-user-meta'>{user.get('job_title', '')} · {user.get('company_name', '')}</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Sign Out", use_container_width=True):
            for key in ("auth_token", "user", "auth_page"):
                st.session_state.pop(key, None)
            st.rerun()

    # ── Fetch data (shared across tabs) ──────────────────────────────────
    candidates_res = api_request("GET", "/api/candidates", token=token)
    _handle_unauthorized(candidates_res)
    candidates = []
    if not (isinstance(candidates_res, dict) and "error" in candidates_res):
        candidates = (candidates_res.get("candidates", [])
                      if isinstance(candidates_res, dict) else candidates_res)
        if not isinstance(candidates, list):
            candidates = []

    for c in candidates:
        if "hiring_score" not in c:
            c["hiring_score"] = hiring_score_engine.calculate_hiring_score(c)["hiring_score"]

    all_skills_flat = [s for c in candidates for s in c.get("skills", [])]
    total_candidates = len(candidates)
    unique_skills    = len(set(all_skills_flat))
    avg_skills       = round(len(all_skills_flat) / total_candidates, 1) if total_candidates else 0

    # ── Page header ───────────────────────────────────────────────────────
    st.markdown("<div class='sh-page-title'>SmartHire AI Platform</div>", unsafe_allow_html=True)
    st.markdown("<div class='sh-page-subtitle'>Analyze candidates, match positions, and identify skill gaps.</div>",
                unsafe_allow_html=True)
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # ── Stats row ─────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class='sh-stats-row'>
        <div class='sh-stat-item'>
            <div class='sh-stat-value'>{total_candidates}</div>
            <div class='sh-stat-label'>Total Candidates</div>
        </div>
        <div class='sh-stat-item'>
            <div class='sh-stat-value'>{unique_skills}</div>
            <div class='sh-stat-label'>Unique Skills</div>
        </div>
        <div class='sh-stat-item'>
            <div class='sh-stat-value'>{avg_skills}</div>
            <div class='sh-stat-label'>Avg Skills / Candidate</div>
        </div>
        <div class='sh-stat-item'>
            <div class='sh-stat-value'>{len(set(c.get("resume_path","") for c in candidates if c.get("resume_path")))}</div>
            <div class='sh-stat-label'>Resumes Parsed</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Upload & Parse", "Candidates", "Analytics", "Job Matcher", "Skill Gap Report", "Interview Assistant"])

    # ════════════════════════════════════════════════════════════════════
    # Tab 1 — Upload & Parse
    # ════════════════════════════════════════════════════════════════════
    with tab1:
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-section-heading'>Resume Upload</div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-page-subtitle' style='margin-bottom:14px;'>Upload PDF, DOCX or TXT files to extract candidate profiles automatically.</div>",
                    unsafe_allow_html=True)

        uploaded_files = st.file_uploader(
            "Drop files here or click to browse",
            accept_multiple_files=True,
            type=["pdf", "docx", "txt"],
            label_visibility="visible",
        )

        if uploaded_files:
            st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
            for uf in uploaded_files:
                ext = uf.name.rsplit(".", 1)[-1].upper()
                st.markdown(f"""
                <div class='sh-file-row'>
                    <span class='sh-file-name'>{uf.name}</span>
                    <span>
                        <span class='sh-badge sh-badge-neutral'>{ext}</span>
                        <span class='sh-file-size'>{_fmt_bytes(uf.size)}</span>
                    </span>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        if st.button("Process Resumes", type="primary", disabled=not uploaded_files):
            pb = st.progress(0)
            status = st.empty()
            results = []
            for i, uf in enumerate(uploaded_files):
                status.markdown(f"<div class='sh-page-subtitle'>Processing <b>{uf.name}</b>…</div>",
                                unsafe_allow_html=True)
                res = api_request("POST", "/api/candidates/upload", token=token,
                                  files={"file": (uf.name, uf.getvalue(), uf.type)})
                _handle_unauthorized(res)
                if "error" in res:
                    results.append({"File": uf.name, "Status": "Error", "Candidate": "—",
                                    "Skills": "—", "Note": res["error"]})
                else:
                    results.append({"File": uf.name, "Status": "Parsed",
                                    "Candidate": res.get("name", "Unknown"),
                                    "Skills": len(res.get("skills", [])),
                                    "Note": ""})
                pb.progress((i + 1) / len(uploaded_files))

            status.empty()
            pb.empty()

            if results:
                st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
                st.markdown("<div class='sh-section-heading'>Results</div>", unsafe_allow_html=True)
                df = pd.DataFrame(results)
                st.dataframe(df, use_container_width=True, hide_index=True)

    # ════════════════════════════════════════════════════════════════════
    # Tab 2 — Candidates
    # ════════════════════════════════════════════════════════════════════
    with tab2:
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        if not candidates:
            if isinstance(candidates_res, dict) and "error" in candidates_res:
                st.error(candidates_res["error"])
            else:
                st.info("No candidates found. Upload some resumes from the Upload & Parse tab.")
        else:
            # Search + filter + sort row
            sc1, sc2, sc3 = st.columns([2, 2, 1.2])
            with sc1:
                search_q = st.text_input("Search candidates", placeholder="Name, email, or file…",
                                         label_visibility="collapsed")
            with sc2:
                skill_filter = st.multiselect("Filter by skill", sorted(set(all_skills_flat)),
                                              label_visibility="collapsed",
                                              placeholder="Filter by skill…")
            with sc3:
                sort_order = st.selectbox("Sort by", ["Default", "Hiring Score"], label_visibility="collapsed")

            # Apply filters
            filtered = candidates
            if search_q:
                q = search_q.lower()
                filtered = [c for c in filtered if
                            q in (_display_name(c.get("name"))).lower() or
                            q in (_display_email(c.get("email"))).lower() or
                            q in (c.get("resume_path") or "").lower()]
            if skill_filter:
                filtered = [c for c in filtered
                            if all(s in c.get("skills", []) for s in skill_filter)]

            if sort_order == "Hiring Score":
                filtered = sorted(filtered, key=lambda x: x.get("hiring_score", 0.0), reverse=True)

            st.markdown(f"<div class='sh-page-subtitle' style='margin-bottom:10px;'>"
                        f"Showing {len(filtered)} of {total_candidates} candidates</div>",
                        unsafe_allow_html=True)

            # Table header
            st.markdown("""
            <div class='sh-table-header'>
                <div class='sh-th sh-th-name'>Candidate</div>
                <div class='sh-th sh-th-email'>Email</div>
                <div class='sh-th' style='min-width:90px;'>Hiring Score</div>
                <div class='sh-th sh-th-skills'>Skills</div>
                <div class='sh-th sh-th-source'>Resume File</div>
            </div>
            """, unsafe_allow_html=True)

            # Candidate rows as expanders
            for c in filtered:
                name   = _display_name(c.get("name"))
                email  = _display_email(c.get("email"))
                phone  = c.get("phone") or "—"
                src    = c.get("resume_path", "—")
                skills = c.get("skills", [])
                hs     = c.get("hiring_score", 0.0)
                hs_badge = _hiring_score_badge(hs)

                with st.expander(f"{name}  ·  {email}  ·  Hiring Score: {hs:.0f}%"):
                    d1, d2, d3 = st.columns([1, 2, 1])

                    with d1:
                        st.markdown("<div class='sh-section-heading'>Overview</div>", unsafe_allow_html=True)
                        st.markdown(f"**Hiring Score:** {hs_badge}", unsafe_allow_html=True)
                        st.markdown(f"**Email:** {email}  \n**Phone:** {phone}  \n**File:** {src}")

                    with d2:
                        st.markdown("<div class='sh-section-heading'>Skills</div>", unsafe_allow_html=True)
                        if skills:
                            st.markdown(_skill_badges(skills, "primary"), unsafe_allow_html=True)
                        else:
                            st.markdown("<span style='color:#64748b;font-size:12px;'>No skills extracted</span>",
                                        unsafe_allow_html=True)

                        exp_list = c.get("experience", [])
                        if exp_list:
                            st.markdown("<div class='sh-section-heading' style='margin-top:12px;'>Experience</div>",
                                        unsafe_allow_html=True)
                            for exp in exp_list[:5]:
                                raw   = exp.get("raw", exp) if isinstance(exp, dict) else exp
                                dates = exp.get("dates", "")  if isinstance(exp, dict) else ""
                                suffix = f" — {dates}" if dates else ""
                                st.markdown(f"<div style='font-size:12px;color:#94a3b8;padding:2px 0;'>{raw}{suffix}</div>",
                                            unsafe_allow_html=True)

                        edu_list = c.get("education", [])
                        if edu_list:
                            st.markdown("<div class='sh-section-heading' style='margin-top:12px;'>Education</div>",
                                        unsafe_allow_html=True)
                            for edu in edu_list:
                                raw = edu.get("raw", edu) if isinstance(edu, dict) else edu
                                st.markdown(f"<div style='font-size:12px;color:#94a3b8;padding:2px 0;'>{raw}</div>",
                                            unsafe_allow_html=True)

                    with d3:
                        st.markdown("<div class='sh-section-heading'>Actions</div>", unsafe_allow_html=True)
                        if st.button("Delete", key=f"del_{c.get('candidate_id')}"):
                            dr = api_request("DELETE", f"/api/candidates/{c.get('candidate_id')}", token=token)
                            _handle_unauthorized(dr)
                            if "error" in dr:
                                st.error(dr["error"])
                            else:
                                st.success("Candidate removed.")
                                st.rerun()

            # Export
            st.markdown("<div class='sh-separator'></div>", unsafe_allow_html=True)
            st.markdown("<div class='sh-section-heading'>Export</div>", unsafe_allow_html=True)
            ex1, ex2, _ = st.columns([1, 1, 3])
            df_exp = pd.DataFrame(filtered)
            for cn in ["skills", "education", "experience", "certifications"]:
                if cn in df_exp.columns:
                    df_exp[cn] = df_exp[cn].apply(lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x)
            with ex1:
                st.download_button("Download CSV", data=df_exp.to_csv(index=False).encode(),
                                   file_name="candidates.csv", mime="text/csv", use_container_width=True)
            with ex2:
                st.download_button("Download JSON", data=json.dumps(filtered, indent=2).encode(),
                                   file_name="candidates.json", mime="application/json", use_container_width=True)

    # ════════════════════════════════════════════════════════════════════
    # Tab 3 — Analytics
    # ════════════════════════════════════════════════════════════════════
    with tab3:
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        ar = api_request("GET", "/api/analytics/skills", token=token)
        _handle_unauthorized(ar)

        if isinstance(ar, dict) and "error" in ar:
            st.warning(f"Could not load analytics: {ar['error']}")
        else:
            skills_data = ar if isinstance(ar, list) else ar.get("skills_frequency", [])

            if not skills_data:
                st.info("No skill data yet. Parse some resumes first.")
            else:
                df_sk = pd.DataFrame(skills_data)
                if "skill" in df_sk.columns:
                    df_sk.columns = [c.title() for c in df_sk.columns]
                df_sk = df_sk.sort_values("Count", ascending=False).reset_index(drop=True)

                # Compact metric row
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.markdown(f"""
                    <div class='sh-card-sm'>
                        <div class='sh-stat-value'>{len(df_sk)}</div>
                        <div class='sh-stat-label'>Unique Skills</div>
                    </div>
                    """, unsafe_allow_html=True)
                with m2:
                    st.markdown(f"""
                    <div class='sh-card-sm'>
                        <div class='sh-stat-value'>{df_sk.iloc[0]["Skill"]}</div>
                        <div class='sh-stat-label'>Most Common</div>
                    </div>
                    """, unsafe_allow_html=True)
                with m3:
                    st.markdown(f"""
                    <div class='sh-card-sm'>
                        <div class='sh-stat-value'>{int(df_sk["Count"].sum())}</div>
                        <div class='sh-stat-label'>Total Occurrences</div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

                ch1, ch2 = st.columns([3, 2])
                with ch1:
                    st.markdown("<div class='sh-section-heading'>Top 20 Skills by Frequency</div>",
                                unsafe_allow_html=True)
                    top20 = df_sk.head(20)
                    fig_bar = px.bar(
                        top20, x="Count", y="Skill", orientation="h",
                        color="Count",
                        color_continuous_scale=[[0, "#312e81"], [1, "#4F46E5"]],
                    )
                    fig_bar.update_layout(
                        template="plotly_dark",
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        yaxis={"categoryorder": "total ascending"},
                        margin=dict(l=0, r=0, t=10, b=0),
                        showlegend=False,
                        coloraxis_showscale=False,
                        height=380,
                        font=dict(family="Inter", size=12),
                    )
                    fig_bar.update_traces(marker_line_width=0)
                    st.plotly_chart(fig_bar, use_container_width=True)

                with ch2:
                    st.markdown("<div class='sh-section-heading'>Skill Distribution</div>",
                                unsafe_allow_html=True)
                    top10 = df_sk.head(10)
                    fig_pie = px.pie(
                        top10, values="Count", names="Skill", hole=0.5,
                        color_discrete_sequence=[
                            "#4F46E5", "#6366f1", "#818cf8", "#a5b4fc",
                            "#312e81", "#3730a3", "#4338CA", "#4F46E5",
                            "#6d28d9", "#7c3aed",
                        ],
                    )
                    fig_pie.update_layout(
                        template="plotly_dark",
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        margin=dict(l=0, r=0, t=10, b=0),
                        showlegend=True,
                        legend=dict(font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
                        height=380,
                        font=dict(family="Inter", size=12),
                    )
                    fig_pie.update_traces(textfont_size=11)
                    st.plotly_chart(fig_pie, use_container_width=True)

                st.markdown("<div class='sh-section-heading'>Skill Frequency Table</div>",
                            unsafe_allow_html=True)
                st.dataframe(df_sk, use_container_width=True, hide_index=True)

    # ════════════════════════════════════════════════════════════════════
    # Tab 4 — Job Matcher
    # ════════════════════════════════════════════════════════════════════
    with tab4:
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-section-heading'>Job Matcher</div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-page-subtitle' style='margin-bottom:14px;'>Find and rank the strongest candidates for open roles using multi-factor AI scoring.</div>",
                    unsafe_allow_html=True)

        mode = st.radio(
            "Matching Mode",
            ["Quick match (free text)", "Match against saved job"],
            horizontal=True,
            key="match_mode_toggle",
            label_visibility="collapsed",
        )
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        if mode == "Quick match (free text)":
            jc1, jc2 = st.columns([4, 1])
            with jc1:
                req_input = st.text_input(
                    "Required skills",
                    value="Python, Machine Learning, SQL",
                    placeholder="e.g. Python, TensorFlow, SQL, Docker",
                    label_visibility="collapsed",
                    key="quick_match_input",
                )
            with jc2:
                match_clicked = st.button("Match & Rank", type="primary", use_container_width=True, key="quick_match_btn")

            if match_clicked:
                if not req_input.strip():
                    st.warning("Enter at least one skill.")
                else:
                    with st.spinner("Ranking candidates…"):
                        mr = api_request("POST", "/api/match", token=token,
                                         json={"required_skills": req_input.strip()})
                    _handle_unauthorized(mr)

                    if isinstance(mr, dict) and "error" in mr:
                        st.error(mr["error"])
                    else:
                        results = mr if isinstance(mr, list) else mr.get("results", [])
                        if not results:
                            st.info("No candidates to match. Upload some resumes first.")
                        else:
                            st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
                            for item in results:
                                name    = _display_name(item.get("candidate_name"))
                                email   = _display_email(item.get("email"))
                                score   = item.get("match_score", 0)
                                matched = item.get("matched_skills", [])
                                missing = item.get("missing_skills", [])
                                bar_col = _score_bar_color(score)
                                badge   = _score_badge(score)

                                matched_html = _skill_badges(matched, "success")
                                missing_html = _skill_badges(missing, "danger")

                                st.markdown(f"""
                                <div class='sh-match-row'>
                                    <div class='sh-match-info'>
                                        <div class='sh-match-name'>{name}</div>
                                        <div class='sh-match-email'>{email}</div>
                                        <div>{matched_html}{missing_html}</div>
                                        <div class='sh-progress-track'>
                                            <div class='sh-progress-fill'
                                                 style='width:{min(score,100):.0f}%;background:{bar_col};'></div>
                                        </div>
                                    </div>
                                    <div class='sh-match-score-col'>{badge}</div>
                                </div>
                                """, unsafe_allow_html=True)

        else:
            # Match against saved job
            jobs_res = api_request("GET", "/api/jobs", token=token)
            _handle_unauthorized(jobs_res)
            jobs_list = jobs_res if isinstance(jobs_res, list) else []

            # Option to create a job position
            with st.expander("＋ Create New Job Posting", expanded=len(jobs_list) == 0):
                with st.form("new_job_form", clear_on_submit=True):
                    f_col1, f_col2 = st.columns(2)
                    with f_col1:
                        new_title = st.text_input("Job Title *", placeholder="e.g. Senior Machine Learning Engineer")
                        new_dept = st.text_input("Department", placeholder="e.g. AI Engineering")
                        new_loc = st.text_input("Location", placeholder="e.g. San Francisco, CA / Remote")
                    with f_col2:
                        new_emp = st.selectbox("Employment Type", ["Full-time", "Contract", "Part-time", "Internship"])
                        new_sen = st.selectbox("Seniority", ["Junior", "Mid-Level", "Senior", "Lead", "Principal"])
                        new_exp = st.number_input("Min Experience (years)", min_value=0, max_value=30, value=2)

                    new_req_skills = st.text_input("Required Skills (comma-separated) *", placeholder="e.g. Python, PyTorch, Kubernetes")
                    new_nice_skills = st.text_input("Nice-to-Have Skills (comma-separated)", placeholder="e.g. Docker, AWS, FastAPI")
                    new_desc = st.text_area("Job Description (optional)", placeholder="Brief summary of role responsibilities…")

                    submit_job = st.form_submit_button("Save Job Posting", type="primary")
                    if submit_job:
                        if not new_title.strip():
                            st.error("Job title is required.")
                        elif not new_req_skills.strip():
                            st.error("At least one required skill is needed.")
                        else:
                            req_list = [s.strip() for s in new_req_skills.split(",") if s.strip()]
                            nice_list = [s.strip() for s in new_nice_skills.split(",") if s.strip()]
                            job_payload = {
                                "title": new_title.strip(),
                                "department": new_dept.strip() or None,
                                "location": new_loc.strip() or None,
                                "employment_type": new_emp,
                                "seniority": new_sen,
                                "min_experience_years": int(new_exp),
                                "required_skills": req_list,
                                "nice_to_have_skills": nice_list,
                                "description": new_desc.strip() or None,
                            }
                            res_job = api_request("POST", "/api/jobs", token=token, json=job_payload)
                            _handle_unauthorized(res_job)
                            if "error" in res_job:
                                st.error(res_job["error"])
                            else:
                                st.success(f"Job posting '{new_title}' created successfully!")
                                st.rerun()

            if not jobs_list:
                st.info("No saved jobs available. Please create a job posting above to match candidates.")
            else:
                job_options = {
                    f"{j['title']} · {j.get('department') or 'General'} ({j.get('location') or 'Remote'})": j
                    for j in jobs_list
                }
                selected_label = st.selectbox("Select Job Position", list(job_options.keys()))
                selected_job = job_options[selected_label]

                # Selected job detail card
                req_badges = _skill_badges(selected_job.get("required_skills", []), "primary") or "<span style='color:#64748b;'>None</span>"
                nice_badges = _skill_badges(selected_job.get("nice_to_have_skills", []), "neutral") or "<span style='color:#64748b;'>None</span>"
                min_exp_str = f"{selected_job.get('min_experience_years', 0)} years" if selected_job.get('min_experience_years') is not None else "Not specified"
                sen_str = selected_job.get("seniority") or "Any"

                st.markdown(f"""
                <div class='sh-card-sm' style='margin-bottom:12px;'>
                    <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'>
                        <div style='font-size:14px;font-weight:600;'>{selected_job['title']}</div>
                        <div style='font-size:12px;color:#94a3b8;'>Min Experience: <b>{min_exp_str}</b> · Seniority: <b>{sen_str}</b></div>
                    </div>
                    <div style='font-size:12px;margin-bottom:4px;'><span style='color:#94a3b8;'>Required:</span> {req_badges}</div>
                    <div style='font-size:12px;'><span style='color:#94a3b8;'>Nice-to-have:</span> {nice_badges}</div>
                </div>
                """, unsafe_allow_html=True)

                col_match_btn, _ = st.columns([2, 3])
                with col_match_btn:
                    run_job_match = st.button("Match Candidates to Job", type="primary", use_container_width=True)

                if run_job_match:
                    with st.spinner(f"Matching candidates for {selected_job['title']}…"):
                        match_res = api_request("POST", f"/api/jobs/{selected_job['job_id']}/match", token=token)
                    _handle_unauthorized(match_res)

                    if isinstance(match_res, dict) and "error" in match_res:
                        st.error(match_res["error"])
                    else:
                        breakdown_list = match_res if isinstance(match_res, list) else []
                        if not breakdown_list:
                            st.info("No candidates found in database to evaluate.")
                        else:
                            st.markdown(f"<div class='sh-page-subtitle' style='margin:14px 0 8px;'>Ranked {len(breakdown_list)} candidates for <b>{selected_job['title']}</b>:</div>",
                                        unsafe_allow_html=True)
                            cand_hs_map = {c.get("candidate_id"): c.get("hiring_score", 70.0) for c in candidates if c.get("candidate_id") is not None}
                            for cand in breakdown_list:
                                c_name = _display_name(cand.get("candidate_name"))
                                c_email = _display_email(cand.get("email"))
                                f_score = cand.get("final_score", 0.0)
                                sk_score = cand.get("skills_score", 0.0)
                                nth_score = cand.get("nice_to_have_score", 0.0)
                                exp_fit = cand.get("experience_fit_score", 0.0)
                                exp_yrs = cand.get("candidate_experience_years", 0.0)

                                cid = cand.get("candidate_id")
                                hs = cand_hs_map.get(cid)
                                if hs is None:
                                    hs = hiring_score_engine.calculate_hiring_score(cand).get("hiring_score", 70.0)
                                blended_score = hiring_score_engine.blend_with_job_match(hs, f_score, hiring_weight=0.35)

                                matched_req = _skill_badges(cand.get("matched_required", []), "success")
                                missing_req = _skill_badges(cand.get("missing_required", []), "danger")
                                matched_nth = _skill_badges(cand.get("matched_nice_to_have", []), "primary")

                                bar_col = _score_bar_color(blended_score)
                                badge = _score_badge(blended_score)

                                nth_markup = f" · <span style='color:#94a3b8;'>Nice-to-Have:</span> {matched_nth}" if matched_nth else ""

                                st.markdown(f"""
                                <div class='sh-match-row'>
                                    <div class='sh-match-info'>
                                        <div class='sh-match-name'>{c_name}</div>
                                        <div class='sh-match-email'>{c_email}</div>
                                        <div class='sh-match-subscores'>
                                            Job Fit: <b>{f_score:.0f}%</b> · Hiring Score: <b>{hs:.0f}%</b> · Blended: <b>{blended_score:.0f}%</b>
                                        </div>
                                        <div class='sh-match-subscores' style='font-size:11px;color:#94a3b8;margin-top:2px;'>
                                            Required Skills: {sk_score:.0f}% · Nice-to-Have: {nth_score:.0f}% · Experience Fit: {exp_fit:.0f}% (~{exp_yrs:.1f} yrs)
                                        </div>
                                        <div>{matched_req}{missing_req}{nth_markup}</div>
                                        <div class='sh-progress-track'>
                                            <div class='sh-progress-fill' style='width:{min(blended_score,100):.0f}%;background:{bar_col};'></div>
                                        </div>
                                    </div>
                                    <div class='sh-match-score-col'>
                                        {badge}
                                        <div style='font-size:10px;color:#94a3b8;margin-top:2px;text-align:center;'>Blended</div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # Tab 5 — Skill Gap Report
    # ════════════════════════════════════════════════════════════════════
    with tab5:
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-section-heading'>Skill Gap Analysis & Pool Readiness</div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-page-subtitle' style='margin-bottom:14px;'>Analyze skills lacking across the candidate pool for any role, view severity breakdowns, and export executive reports.</div>",
                    unsafe_allow_html=True)

        jobs_res = api_request("GET", "/api/jobs", token=token)
        _handle_unauthorized(jobs_res)
        jobs_list = jobs_res if isinstance(jobs_res, list) else []

        if not jobs_list:
            st.info("No job postings found. Create a job position in the Job Matcher tab first.")
        else:
            job_map = {f"{j['title']} ({j.get('department') or 'General'} · {j.get('seniority') or 'Mid'})": j for j in jobs_list}
            selected_label = st.selectbox("Select Target Job Position", list(job_map.keys()), key="gap_report_job_select")
            selected_job = job_map[selected_label]
            selected_job_id = selected_job["job_id"]

            with st.spinner("Analyzing candidate pool skill gaps…"):
                report_res = api_request("GET", f"/api/jobs/{selected_job_id}/skill-gap-report", token=token)
            _handle_unauthorized(report_res)

            if isinstance(report_res, dict) and "error" in report_res:
                st.error(report_res["error"])
            else:
                report = report_res
                readiness = report.get("pool_readiness_score", 0.0)
                analyzed_count = report.get("total_candidates_analyzed", 0)
                crit_gaps = report.get("critical_gaps", [])
                mod_gaps = report.get("moderate_gaps", [])
                min_gaps = report.get("minor_gaps", [])
                well_cov = report.get("well_covered_skills", [])

                # Summary Metric Cards
                k1, k2, k3, k4 = st.columns(4)
                with k1:
                    readiness_col = "#10B981" if readiness >= 70 else "#F59E0B" if readiness >= 40 else "#F43F5E"
                    st.markdown(f"""
                    <div class='sh-card-sm'>
                        <div class='sh-stat-value' style='color:{readiness_col};'>{readiness:.1f}%</div>
                        <div class='sh-stat-label'>Pool Readiness Score</div>
                    </div>
                    """, unsafe_allow_html=True)
                with k2:
                    st.markdown(f"""
                    <div class='sh-card-sm'>
                        <div class='sh-stat-value'>{analyzed_count}</div>
                        <div class='sh-stat-label'>Candidates Evaluated</div>
                    </div>
                    """, unsafe_allow_html=True)
                with k3:
                    st.markdown(f"""
                    <div class='sh-card-sm'>
                        <div class='sh-stat-value' style='color:#F43F5E;'>{len(crit_gaps)}</div>
                        <div class='sh-stat-label'>Critical Gaps (≥50%)</div>
                    </div>
                    """, unsafe_allow_html=True)
                with k4:
                    st.markdown(f"""
                    <div class='sh-card-sm'>
                        <div class='sh-stat-value' style='color:#F59E0B;'>{len(mod_gaps)}</div>
                        <div class='sh-stat-label'>Moderate Gaps (20–49%)</div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

                # Visual Plotly Chart of Skill Gaps
                all_gaps = crit_gaps + mod_gaps + min_gaps
                if all_gaps:
                    st.markdown("<div class='sh-section-heading'>Skill Deficiencies by Severity</div>", unsafe_allow_html=True)
                    df_gaps = pd.DataFrame(all_gaps)
                    df_gaps["severity"] = df_gaps["severity"].str.capitalize()
                    df_gaps = df_gaps.sort_values("missing_percentage", ascending=True)

                    fig_gaps = px.bar(
                        df_gaps,
                        x="missing_percentage",
                        y="skill",
                        color="severity",
                        orientation="h",
                        color_discrete_map={
                            "Critical": "#F43F5E",
                            "Moderate": "#F59E0B",
                            "Minor": "#6366F1",
                        },
                        labels={
                            "missing_percentage": "Candidates Missing Skill (%)",
                            "skill": "Skill",
                            "severity": "Severity",
                        },
                        hover_data={"missing_count": True, "category": True},
                    )
                    fig_gaps.update_layout(
                        template="plotly_dark",
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        margin=dict(l=0, r=0, t=10, b=0),
                        height=max(260, len(df_gaps) * 34),
                        font=dict(family="Inter", size=12),
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1,
                            bgcolor="rgba(0,0,0,0)",
                            font=dict(size=11),
                        ),
                    )
                    fig_gaps.update_xaxes(range=[0, 105], showgrid=True, gridcolor="rgba(255,255,255,0.08)")
                    fig_gaps.update_yaxes(showgrid=False)
                    st.plotly_chart(fig_gaps, use_container_width=True)
                else:
                    st.info("No skill gaps detected in the candidate pool for this role.")

                # Well-Covered Skills Section
                st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
                st.markdown("<div class='sh-section-heading'>Well-Covered Required Skills (≥80% Coverage)</div>", unsafe_allow_html=True)
                if well_cov:
                    wc_html = "".join(
                        f"<span class='sh-badge sh-badge-success' style='font-size:12px;padding:4px 10px;margin-right:8px;margin-bottom:6px;display:inline-block;'>"
                        f"✓ {w['skill']} ({w['coverage_percentage']:.0f}% covered)</span>"
                        for w in well_cov
                    )
                    st.markdown(f"<div>{wc_html}</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='color:#94a3b8;font-size:12px;'>No required skills currently meet the 80% coverage threshold.</span>", unsafe_allow_html=True)

                # Export Section
                st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)
                st.markdown("<div class='sh-section-heading'>Export Executive Report</div>", unsafe_allow_html=True)
                exp1, exp2, _ = st.columns([1.2, 1.5, 2.5])
                with exp1:
                    csv_resp = requests.get(
                        f"{API_BASE_URL}/api/jobs/{selected_job_id}/skill-gap-report/export?format=csv",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if csv_resp.status_code == 200:
                        st.download_button(
                            "⬇ Download CSV",
                            data=csv_resp.content,
                            file_name=f"skill_gap_report_job_{selected_job_id}.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )
                with exp2:
                    docx_resp = requests.get(
                        f"{API_BASE_URL}/api/jobs/{selected_job_id}/skill-gap-report/export?format=docx",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if docx_resp.status_code == 200:
                        st.download_button(
                            "⬇ Download Word (.docx)",
                            data=docx_resp.content,
                            file_name=f"skill_gap_report_job_{selected_job_id}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                        )

                # Candidate Gap Inspector
                st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
                with st.expander("🔍 Inspect Individual Candidate Development Plan", expanded=False):
                    cand_lookup = {
                        f"{_display_name(c.get('name'))} ({_display_email(c.get('email'))})": c.get("candidate_id")
                        for c in candidates if c.get("candidate_id") is not None
                    }
                    if cand_lookup:
                        cand_label = st.selectbox("Select Candidate to Inspect", list(cand_lookup.keys()), key="gap_cand_select")
                        selected_cid = cand_lookup[cand_label]
                        cg_res = api_request("GET", f"/api/jobs/{selected_job_id}/skill-gap-report/candidates/{selected_cid}", token=token)
                        _handle_unauthorized(cg_res)
                        if isinstance(cg_res, dict) and "error" not in cg_res:
                            gc1, gc2 = st.columns(2)
                            with gc1:
                                st.markdown("<div class='sh-section-heading' style='color:#F43F5E;'>Missing Required Skills</div>", unsafe_allow_html=True)
                                req_miss = cg_res.get("missing_required", [])
                                if req_miss:
                                    st.markdown(_skill_badges(req_miss, "danger"), unsafe_allow_html=True)
                                else:
                                    st.markdown("<span style='color:#10B981;font-weight:500;font-size:12px;'>✓ All required skills satisfied!</span>", unsafe_allow_html=True)
                            with gc2:
                                st.markdown("<div class='sh-section-heading' style='color:#6366F1;'>Missing Nice-to-Have Skills</div>", unsafe_allow_html=True)
                                nth_miss = cg_res.get("missing_nice_to_have", [])
                                if nth_miss:
                                    st.markdown(_skill_badges(nth_miss, "primary"), unsafe_allow_html=True)
                                else:
                                    st.markdown("<span style='color:#94a3b8;font-size:12px;'>No optional skills missing.</span>", unsafe_allow_html=True)

                            # Full Development Report
                            st.markdown("---")
                            st.markdown("<div class='sh-section-heading' style='font-size:15px;margin-bottom:12px;'>Full Development Report</div>", unsafe_allow_html=True)
                            dev_res = api_request("GET", f"/api/jobs/{selected_job_id}/skill-gap-report/candidates/{selected_cid}/development-report", token=token)
                            _handle_unauthorized(dev_res)
                            if isinstance(dev_res, dict) and "error" not in dev_res:
                                # Overall Fit Score and Readiness badge
                                fit_score = dev_res.get("overall_fit_score", 0.0)
                                readiness = dev_res.get("readiness_level", "not_ready")
                                readiness_styles = {
                                    "ready": ("#10B981", "rgba(16,185,129,0.15)", "#6ee7b7"),
                                    "near_ready": ("#6366F1", "rgba(99,102,241,0.18)", "#a5b4fc"),
                                    "developing": ("#F59E0B", "rgba(245,158,11,0.18)", "#fcd34d"),
                                    "not_ready": ("#F43F5E", "rgba(244,63,94,0.15)", "#fda4af"),
                                }
                                border_c, bg_c, text_c = readiness_styles.get(readiness, ("#94a3b8", "rgba(255,255,255,0.06)", "#cbd5e1"))
                                readiness_title = readiness.replace("_", " ").title()

                                f_col1, f_col2 = st.columns([1, 1])
                                with f_col1:
                                    st.markdown(
                                        f"<div style='font-size:12px;color:#94a3b8;margin-bottom:2px;'>Overall Fit Score</div>"
                                        f"<div style='font-size:22px;font-weight:700;color:{_score_bar_color(fit_score)};'>{fit_score:.1f}%</div>",
                                        unsafe_allow_html=True,
                                    )
                                with f_col2:
                                    st.markdown(
                                        f"<div style='font-size:12px;color:#94a3b8;margin-bottom:4px;'>Readiness Level</div>"
                                        f"<span style='display:inline-block;padding:4px 12px;border-radius:9999px;background:{bg_c};color:{text_c};border:1px solid {border_c};font-weight:600;font-size:13px;'>{readiness_title}</span>",
                                        unsafe_allow_html=True,
                                    )

                                st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

                                # Matched Skills (positive-styled badges)
                                mc1, mc2 = st.columns(2)
                                with mc1:
                                    st.markdown("<div class='sh-section-heading' style='color:#10B981;'>Matched Required Skills</div>", unsafe_allow_html=True)
                                    m_req = dev_res.get("matched_required", [])
                                    if m_req:
                                        st.markdown(_skill_badges(m_req, "success"), unsafe_allow_html=True)
                                    else:
                                        st.markdown("<span style='color:#94a3b8;font-size:12px;'>None</span>", unsafe_allow_html=True)
                                with mc2:
                                    st.markdown("<div class='sh-section-heading' style='color:#10B981;'>Matched Nice-to-Have Skills</div>", unsafe_allow_html=True)
                                    m_nth = dev_res.get("matched_nice_to_have", [])
                                    if m_nth:
                                        st.markdown(_skill_badges(m_nth, "success"), unsafe_allow_html=True)
                                    else:
                                        st.markdown("<span style='color:#94a3b8;font-size:12px;'>None</span>", unsafe_allow_html=True)

                                st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

                                # Missing Skills with Pool-Relative Priority
                                st.markdown("<div class='sh-section-heading'>Skill Gaps with Pool-Relative Priority</div>", unsafe_allow_html=True)
                                p_col1, p_col2 = st.columns(2)
                                priority_classes = {"high": "danger", "medium": "primary", "low": "neutral"}
                                with p_col1:
                                    st.markdown("<div style='font-size:12px;font-weight:600;color:#cbd5e1;margin-bottom:6px;'>Missing Required</div>", unsafe_allow_html=True)
                                    miss_req_details = dev_res.get("missing_required", [])
                                    if miss_req_details:
                                        badges_html = "".join(
                                            f"<span class='sh-badge sh-badge-{priority_classes.get(item.get('priority'), 'neutral')}' style='margin-right:6px;margin-bottom:6px;display:inline-block;' title='{item.get('priority', '').title()} priority ({item.get('pool_coverage_percentage', 0):.0f}% pool coverage)'>"
                                            f"{item.get('skill')} <small style='opacity:0.85;'>[{item.get('priority', '').upper()} &bull; {item.get('pool_coverage_percentage', 0):.0f}% pool]</small></span>"
                                            for item in miss_req_details
                                        )
                                        st.markdown(badges_html, unsafe_allow_html=True)
                                    else:
                                        st.markdown("<span style='color:#10B981;font-size:12px;'>✓ None missing</span>", unsafe_allow_html=True)
                                with p_col2:
                                    st.markdown("<div style='font-size:12px;font-weight:600;color:#cbd5e1;margin-bottom:6px;'>Missing Nice-to-Have</div>", unsafe_allow_html=True)
                                    miss_nth_details = dev_res.get("missing_nice_to_have", [])
                                    if miss_nth_details:
                                        badges_html = "".join(
                                            f"<span class='sh-badge sh-badge-{priority_classes.get(item.get('priority'), 'neutral')}' style='margin-right:6px;margin-bottom:6px;display:inline-block;' title='{item.get('priority', '').title()} priority ({item.get('pool_coverage_percentage', 0):.0f}% pool coverage)'>"
                                            f"{item.get('skill')} <small style='opacity:0.85;'>[{item.get('priority', '').upper()} &bull; {item.get('pool_coverage_percentage', 0):.0f}% pool]</small></span>"
                                            for item in miss_nth_details
                                        )
                                        st.markdown(badges_html, unsafe_allow_html=True)
                                    else:
                                        st.markdown("<span style='color:#94a3b8;font-size:12px;'>None missing</span>", unsafe_allow_html=True)

                                st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

                                # Development Recommendations
                                st.markdown("<div class='sh-section-heading'>Development Recommendations</div>", unsafe_allow_html=True)
                                recs = dev_res.get("development_recommendations", [])
                                if recs:
                                    for idx, rec in enumerate(recs, 1):
                                        st.markdown(f"<div style='font-size:13px;color:#e2e8f0;margin-bottom:6px;'><b>{idx}.</b> {rec}</div>", unsafe_allow_html=True)
                                else:
                                    st.markdown("<span style='color:#94a3b8;font-size:12px;'>No skill gaps identified.</span>", unsafe_allow_html=True)

                                # Export Single Candidate Report (CSV, DOCX)
                                st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
                                dcol1, dcol2, _ = st.columns([1.2, 1.5, 2.5])
                                with dcol1:
                                    c_csv_resp = requests.get(
                                        f"{API_BASE_URL}/api/jobs/{selected_job_id}/skill-gap-report/candidates/{selected_cid}/development-report/export?format=csv",
                                        headers={"Authorization": f"Bearer {token}"},
                                    )
                                    if c_csv_resp.status_code == 200:
                                        st.download_button(
                                            "⬇ Download CSV",
                                            data=c_csv_resp.content,
                                            file_name=f"development_report_candidate_{selected_cid}_job_{selected_job_id}.csv",
                                            mime="text/csv",
                                            key=f"dl_cand_dev_csv_{selected_cid}",
                                            use_container_width=True,
                                        )
                                with dcol2:
                                    c_docx_resp = requests.get(
                                        f"{API_BASE_URL}/api/jobs/{selected_job_id}/skill-gap-report/candidates/{selected_cid}/development-report/export?format=docx",
                                        headers={"Authorization": f"Bearer {token}"},
                                    )
                                    if c_docx_resp.status_code == 200:
                                        st.download_button(
                                            "⬇ Download Word (.docx)",
                                            data=c_docx_resp.content,
                                            file_name=f"development_report_candidate_{selected_cid}_job_{selected_job_id}.docx",
                                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                            key=f"dl_cand_dev_docx_{selected_cid}",
                                            use_container_width=True,
                                        )
                    else:
                        st.info("No candidates available to inspect.")

                    # Batch Development Reports
                    st.markdown("---")
                    st.markdown("<div class='sh-section-heading' style='font-size:14px;margin-bottom:8px;'>Batch Development Reports (Top Ranked Candidates)</div>", unsafe_allow_html=True)
                    bc1, bc2 = st.columns([1.2, 2.0])
                    with bc1:
                        top_n = st.number_input("Top N Candidates", min_value=1, max_value=50, value=10, step=1, key="dev_batch_top_n")
                    with bc2:
                        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                        batch_zip_resp = requests.get(
                            f"{API_BASE_URL}/api/jobs/{selected_job_id}/skill-gap-report/development-reports/batch-export?top_n={top_n}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        if batch_zip_resp.status_code == 200:
                            st.download_button(
                                "📦 Generate Batch Reports (ZIP)",
                                data=batch_zip_resp.content,
                                file_name=f"development_reports_top{top_n}_job_{selected_job_id}.zip",
                                mime="application/zip",
                                key=f"dl_batch_zip_{selected_job_id}_{top_n}",
                                use_container_width=True,
                            )

    # ════════════════════════════════════════════════════════════════════
    # Tab 6 — Interview Assistant
    # ════════════════════════════════════════════════════════════════════
    with tab6:
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-section-heading'>Interview Question Generator</div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-page-subtitle' style='margin-bottom:14px;'>Generate tailored technical, behavioral, and scenario-based questions grounded in role requirements.</div>", unsafe_allow_html=True)

        jobs_res = api_request("GET", "/api/jobs", token=token)
        _handle_unauthorized(jobs_res)
        jobs_list = jobs_res if isinstance(jobs_res, list) else []

        if not jobs_list:
            st.info("No saved job positions found. Please create one in the Job Matcher tab first.")
        else:
            job_options = {
                f"{j['title']} · {j.get('department') or 'General'} ({j.get('location') or 'Remote'})": j
                for j in jobs_list
            }
            selected_label = st.selectbox("Select Job Position", list(job_options.keys()), key="iq_job_select")
            selected_job = job_options[selected_label]
            selected_job_id = selected_job["job_id"]

            iq_c1, iq_c2 = st.columns([1.5, 1])
            with iq_c1:
                q_type = st.selectbox("Question Type", ["Technical", "Behavioral", "Scenario-based"], key="iq_type_select")
            with iq_c2:
                q_count = st.number_input("Number of Questions", min_value=1, max_value=10, value=3, step=1, key="iq_count_input")

            if st.button("Generate Questions", type="primary", key="iq_generate_btn"):
                with st.spinner("Generating role-specific questions..."):
                    res = api_request(
                        "GET",
                        f"/api/jobs/{selected_job_id}/interview-questions?question_type={q_type}&count={q_count}",
                        token=token,
                    )
                    _handle_unauthorized(res)
                    if isinstance(res, dict) and "error" in res:
                        st.error(f"Error: {res['error']}")
                    elif isinstance(res, dict) and "questions" in res:
                        st.session_state[f"iq_questions_{selected_job_id}"] = res
                    else:
                        st.error("Failed to generate questions. Please ensure ANTHROPIC_API_KEY is configured.")

            saved_q = st.session_state.get(f"iq_questions_{selected_job_id}")
            if saved_q and "questions" in saved_q:
                st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:14px;font-weight:600;margin-bottom:10px;'>Generated {saved_q.get('question_type')} Questions ({len(saved_q['questions'])})</div>", unsafe_allow_html=True)
                for q in saved_q["questions"]:
                    q_num = q.get("question_number", 1)
                    q_text = q.get("question_text", "")
                    q_t = q.get("question_type", q_type)
                    s_type = q.get("sub_type", "General")
                    est_dur = q.get("estimated_duration", "3-5 min response")
                    st.markdown(f"""
                    <div class='sh-card-sm' style='margin-bottom:10px;padding:14px 16px;'>
                        <div style='font-size:14px;font-weight:600;color:#f8fafc;margin-bottom:6px;'><b>{q_num}.</b> {q_text}</div>
                        <div style='font-size:12px;color:#94a3b8;'>{q_t} • {s_type} • {est_dur}</div>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-section-heading'>Practice Question Generator (MCQ + Difficulty)</div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-page-subtitle' style='margin-bottom:14px;'>Generate difficulty-leveled practice questions, as open-ended prompts or multiple choice with answers.</div>", unsafe_allow_html=True)

        if not jobs_list:
            st.info("No saved job positions found. Please create one in the Job Matcher tab first.")
        else:
            pq_job_label = st.selectbox("Select Job Position", list(job_options.keys()), key="pq_job_select")
            pq_job = job_options[pq_job_label]
            pq_job_id = pq_job["job_id"]

            pq_c1, pq_c2, pq_c3, pq_c4 = st.columns([1.3, 1, 1.2, 1])
            with pq_c1:
                pq_type = st.selectbox("Question Type", ["Technical", "Behavioral", "Scenario-based"], key="pq_type_select")
            with pq_c2:
                pq_difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1, key="pq_difficulty_select")
            with pq_c3:
                pq_format = st.selectbox("Format", ["Open-ended", "Multiple Choice"], key="pq_format_select")
            with pq_c4:
                pq_count = st.number_input("Count", min_value=1, max_value=10, value=3, step=1, key="pq_count_input")

            if st.button("Generate Practice Questions", type="primary", key="pq_generate_btn"):
                with st.spinner(f"Generating {pq_difficulty} {pq_format} questions..."):
                    res = api_request(
                        "GET",
                        f"/api/jobs/{pq_job_id}/interview-questions/practice"
                        f"?question_type={pq_type}&difficulty={pq_difficulty}&question_format={pq_format}&count={pq_count}",
                        token=token,
                    )
                    _handle_unauthorized(res)
                    if isinstance(res, dict) and "error" in res:
                        st.error(f"Error: {res['error']}")
                    elif isinstance(res, dict) and "questions" in res:
                        st.session_state[f"pq_questions_{pq_job_id}"] = res
                    else:
                        st.error("Failed to generate practice questions. Please ensure an AI API key is configured.")

            saved_pq = st.session_state.get(f"pq_questions_{pq_job_id}")
            if saved_pq and "questions" in saved_pq:
                st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div style='font-size:14px;font-weight:600;margin-bottom:10px;'>"
                    f"Generated {saved_pq.get('difficulty')} {saved_pq.get('question_format')} Questions "
                    f"({len(saved_pq['questions'])})</div>",
                    unsafe_allow_html=True,
                )
                for q in saved_pq["questions"]:
                    q_num = q.get("question_number", 1)
                    q_text = q.get("question_text", "")
                    q_t = q.get("question_type", pq_type)
                    s_type = q.get("sub_type", "General")
                    est_dur = q.get("estimated_duration", "")
                    diff = q.get("difficulty", pq_difficulty)
                    if q.get("question_format") == "Multiple Choice" and q.get("options"):
                        options_html = "".join(
                            f"<div style='padding:6px 10px;margin:4px 0;border-radius:6px;background:rgba(148,163,184,0.08);'>"
                            f"<b>{opt.get('label')}.</b> {opt.get('text')}</div>"
                            for opt in q["options"]
                        )
                        st.markdown(f"""
                        <div class='sh-card-sm' style='margin-bottom:10px;padding:14px 16px;'>
                            <div style='font-size:14px;font-weight:600;color:#f8fafc;margin-bottom:6px;'><b>{q_num}.</b> {q_text}</div>
                            <div style='font-size:12px;color:#94a3b8;margin-bottom:8px;'>{q_t} • {s_type} • {diff} • {est_dur}</div>
                            {options_html}
                        </div>
                        """, unsafe_allow_html=True)
                        with st.expander(f"Show answer — Q{q_num}"):
                            st.markdown(f"**Correct option: {q.get('correct_option', '—')}**")
                            if q.get("explanation"):
                                st.markdown(q["explanation"])
                    else:
                        st.markdown(f"""
                        <div class='sh-card-sm' style='margin-bottom:10px;padding:14px 16px;'>
                            <div style='font-size:14px;font-weight:600;color:#f8fafc;margin-bottom:6px;'><b>{q_num}.</b> {q_text}</div>
                            <div style='font-size:12px;color:#94a3b8;'>{q_t} • {s_type} • {diff} • {est_dur}</div>
                        </div>
                        """, unsafe_allow_html=True)

        # ── AI Interview Simulation ──────────────────────────────────────────
        st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-section-heading'>AI Interview Simulation</div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-page-subtitle' style='margin-bottom:14px;'>Conduct an interactive, role-specific simulated interview with AI-generated questions and natural follow-ups.</div>", unsafe_allow_html=True)

        sim_c1, sim_c2 = st.columns(2)
        with sim_c1:
            sim_cand_opts = {
                f"{_display_name(c.get('name'))} ({_display_email(c.get('email'))})": c.get("candidate_id")
                for c in candidates if c.get("candidate_id") is not None
            }
            if sim_cand_opts:
                sim_cand_label = st.selectbox("Select Candidate for Interview", list(sim_cand_opts.keys()), key="sim_cand_select")
                sim_cand_id = sim_cand_opts[sim_cand_label]
            else:
                st.info("No candidates available.")
                sim_cand_id = None

        with sim_c2:
            if jobs_list:
                sim_job_opts = {
                    f"{j['title']} · {j.get('department') or 'General'}": j["job_id"]
                    for j in jobs_list
                }
                sim_job_label = st.selectbox("Select Target Job Position", list(sim_job_opts.keys()), key="sim_job_select")
                sim_job_id = sim_job_opts[sim_job_label]
            else:
                st.info("No jobs available.")
                sim_job_id = None

        active_session_id = st.session_state.get("active_interview_session_id")

        sim_btn_c1, sim_btn_c2 = st.columns([1.5, 1.5])
        with sim_btn_c1:
            if st.button("🚀 Start Interview", type="primary", key="btn_start_interview"):
                if not sim_cand_id or not sim_job_id:
                    st.error("Please select both a candidate and a job position.")
                else:
                    with st.spinner("Initializing interview session..."):
                        create_payload = {"candidate_id": sim_cand_id, "job_id": sim_job_id}
                        create_res = api_request("POST", "/api/interview-sessions", token=token, json=create_payload)
                        _handle_unauthorized(create_res)
                        if isinstance(create_res, dict) and "session_id" in create_res:
                            new_sess_id = create_res["session_id"]
                            st.session_state["active_interview_session_id"] = new_sess_id
                            # Generate opening line
                            resp_res = api_request("POST", f"/api/interview-sessions/{new_sess_id}/respond", token=token, json={})
                            _handle_unauthorized(resp_res)
                            if isinstance(resp_res, dict) and "transcript" in resp_res:
                                st.session_state[f"session_data_{new_sess_id}"] = resp_res
                            st.rerun()
                        else:
                            st.error(f"Failed to start session: {create_res.get('error', 'Unknown error')}")

        with sim_btn_c2:
            if active_session_id:
                if st.button("⏹ End Interview", key="btn_end_interview"):
                    with st.spinner("Concluding interview..."):
                        end_res = api_request("POST", f"/api/interview-sessions/{active_session_id}/complete", token=token)
                        _handle_unauthorized(end_res)
                        st.session_state.pop("active_interview_session_id", None)
                        st.session_state.pop(f"session_data_{active_session_id}", None)
                        st.success("Interview session marked as completed.")
                        st.rerun()

        # Render Active Interview Chat
        if active_session_id:
            session_data = api_request("GET", f"/api/interview-sessions/{active_session_id}", token=token)
            _handle_unauthorized(session_data)
            if isinstance(session_data, dict) and "transcript" in session_data:
                transcript = session_data.get("transcript", [])
                st.markdown(f"""
                <div class='sh-card-sm' style='margin-top:12px;margin-bottom:12px;padding:10px 14px;'>
                    <span style='color:#94a3b8;font-size:12px;'>Active Session #{active_session_id} · Candidate: <b>{session_data.get('candidate_name')}</b> · Role: <b>{session_data.get('job_title')}</b></span>
                </div>
                """, unsafe_allow_html=True)

                chat_container = st.container()
                with chat_container:
                    for msg in transcript:
                        role = msg.get("role")
                        content = msg.get("content", "")
                        if role == "interviewer":
                            with st.chat_message("assistant"):
                                st.markdown(content)
                        else:
                            with st.chat_message("user"):
                                st.markdown(content)

                if session_data.get("status") != "completed":
                    user_input = st.chat_input("Type candidate's response here...", key="interview_chat_input")
                    if user_input:
                        with st.spinner("Interviewer is evaluating and responding..."):
                            resp_res = api_request(
                                "POST",
                                f"/api/interview-sessions/{active_session_id}/respond",
                                token=token,
                                json={"message": user_input},
                            )
                            _handle_unauthorized(resp_res)
                            st.rerun()

        # ── Candidate Pipeline (ATS Status) ──────────────────────────────────
        st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-section-heading'>Candidate Pipeline (ATS Status)</div>", unsafe_allow_html=True)
        st.markdown("<div class='sh-page-subtitle' style='margin-bottom:14px;'>Track and advance candidates through the interview lifecycle.</div>", unsafe_allow_html=True)

        with st.expander("➕ Add Candidate to Interview Pipeline", expanded=False):
            with st.form("add_pipeline_form", clear_on_submit=True):
                pipe_c1, pipe_c2 = st.columns(2)
                with pipe_c1:
                    cand_opts = {
                        f"{_display_name(c.get('name'))} ({_display_email(c.get('email'))})": c.get("candidate_id")
                        for c in candidates if c.get("candidate_id") is not None
                    }
                    if cand_opts:
                        sel_cand_label = st.selectbox("Select Candidate", list(cand_opts.keys()), key="pipe_cand_select")
                        sel_cand_id = cand_opts[sel_cand_label]
                    else:
                        st.info("No candidates found.")
                        sel_cand_id = None
                with pipe_c2:
                    if jobs_list:
                        pipe_job_opts = {
                            f"{j['title']} · {j.get('department') or 'General'}": j["job_id"]
                            for j in jobs_list
                        }
                        sel_pipe_job_label = st.selectbox("Assign to Job Position", list(pipe_job_opts.keys()), key="pipe_job_select")
                        sel_pipe_job_id = pipe_job_opts[sel_pipe_job_label]
                    else:
                        st.info("No jobs available.")
                        sel_pipe_job_id = None

                schedule_date = st.date_input("Scheduled Date (optional, leave blank for in-progress)", value=None, key="pipe_sched_date")
                submit_pipeline = st.form_submit_button("Add to Pipeline", type="primary")

                if submit_pipeline:
                    if not sel_cand_id or not sel_pipe_job_id:
                        st.error("Please select both a candidate and a job position.")
                    else:
                        payload = {
                            "candidate_id": sel_cand_id,
                            "job_id": sel_pipe_job_id,
                            "scheduled_at": f"{schedule_date.isoformat()}T09:00:00" if schedule_date else None,
                        }
                        res = api_request("POST", "/api/interview-sessions", token=token, json=payload)
                        _handle_unauthorized(res)
                        if isinstance(res, dict) and "error" in res:
                            st.error(f"Failed to add to pipeline: {res['error']}")
                        else:
                            st.success("Candidate successfully added to interview pipeline!")
                            st.rerun()

        filter_col1, _ = st.columns([2, 2])
        with filter_col1:
            filter_job_opts = {"All Job Positions": None}
            for j in jobs_list:
                filter_job_opts[f"{j['title']} · {j.get('department') or 'General'}"] = j["job_id"]
            selected_filter_label = st.selectbox("Filter Pipeline by Job", list(filter_job_opts.keys()), key="pipe_filter_job")
            filtered_job_id = filter_job_opts[selected_filter_label]

        sessions_url = f"/api/interview-sessions?job_id={filtered_job_id}" if filtered_job_id is not None else "/api/interview-sessions"
        pipe_res = api_request("GET", sessions_url, token=token)
        _handle_unauthorized(pipe_res)
        sessions_list = pipe_res if isinstance(pipe_res, list) else []

        if not sessions_list:
            st.info("No candidate interview sessions found.")
        else:
            status_styles = {
                "scheduled": ("#6366F1", "rgba(99,102,241,0.18)", "#a5b4fc"),
                "in_progress": ("#F59E0B", "rgba(245,158,11,0.18)", "#fcd34d"),
                "completed": ("#10B981", "rgba(16,185,129,0.15)", "#6ee7b7"),
            }
            for s in sessions_list:
                s_id = s.get("session_id")
                c_name = s.get("candidate_name") or f"Candidate #{s.get('candidate_id')}"
                j_title = s.get("job_title") or "Unknown Job"
                stat = s.get("status", "scheduled")
                upd_time = s.get("updated_at", "")[:16].replace("T", " ")
                border_c, bg_c, text_c = status_styles.get(stat, ("#94a3b8", "rgba(255,255,255,0.06)", "#94a3b8"))
                stat_badge = f"<span style='display:inline-block;padding:3px 10px;border-radius:9999px;background:{bg_c};color:{text_c};border:1px solid {border_c};font-weight:600;font-size:12px;'>{stat.replace('_', ' ').title()}</span>"

                sc_col1, sc_col2 = st.columns([3.5, 1])
                with sc_col1:
                    st.markdown(f"""
                    <div class='sh-card-sm' style='margin-bottom:8px;padding:12px 16px;'>
                        <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;'>
                            <div style='font-size:14px;font-weight:600;color:#f8fafc;'>{c_name} · <span style='font-weight:400;color:#94a3b8;'>{j_title}</span></div>
                            <div>{stat_badge}</div>
                        </div>
                        <div style='font-size:12px;color:#64748b;'>Last updated: {upd_time}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with sc_col2:
                    if stat != "completed":
                        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                        if st.button("Mark Completed", key=f"mark_comp_{s_id}", use_container_width=True):
                            comp_res = api_request("POST", f"/api/interview-sessions/{s_id}/complete", token=token)
                            _handle_unauthorized(comp_res)
                            st.rerun()





# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    token = st.session_state.get("auth_token")
    if not token:
        if st.session_state.get("auth_page") == "register":
            show_register()
        else:
            show_login()
        return
    show_dashboard()


if __name__ == "__main__":
    main()
