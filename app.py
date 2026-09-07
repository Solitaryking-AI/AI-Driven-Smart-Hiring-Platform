import streamlit as st
import requests
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go

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

def _score_badge(score: float) -> str:
    cls = "sh-score-high" if score >= 70 else "sh-score-mid" if score >= 40 else "sh-score-low"
    return f"<span class='{cls}'>{score:.0f}%</span>"

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
    tab1, tab2, tab3, tab4 = st.tabs(["Upload & Parse", "Candidates", "Analytics", "Job Matcher"])

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
            # Search + filter row
            sc1, sc2, sc3 = st.columns([2, 2, 1])
            with sc1:
                search_q = st.text_input("Search candidates", placeholder="Name, email, or file…",
                                         label_visibility="collapsed")
            with sc2:
                skill_filter = st.multiselect("Filter by skill", sorted(set(all_skills_flat)),
                                              label_visibility="collapsed",
                                              placeholder="Filter by skill…")

            # Apply filters
            filtered = candidates
            if search_q:
                q = search_q.lower()
                filtered = [c for c in filtered if
                            q in (c.get("name") or "").lower() or
                            q in (c.get("email") or "").lower() or
                            q in (c.get("resume_path") or "").lower()]
            if skill_filter:
                filtered = [c for c in filtered
                            if all(s in c.get("skills", []) for s in skill_filter)]

            st.markdown(f"<div class='sh-page-subtitle' style='margin-bottom:10px;'>"
                        f"Showing {len(filtered)} of {total_candidates} candidates</div>",
                        unsafe_allow_html=True)

            # Table header
            st.markdown("""
            <div class='sh-table-header'>
                <div class='sh-th sh-th-name'>Candidate</div>
                <div class='sh-th sh-th-email'>Email</div>
                <div class='sh-th sh-th-skills'>Skills</div>
                <div class='sh-th sh-th-source'>Resume File</div>
            </div>
            """, unsafe_allow_html=True)

            # Candidate rows as expanders
            for c in filtered:
                name   = c.get("name", "Unknown Candidate")
                email  = c.get("email", "—")
                phone  = c.get("phone", "—")
                src    = c.get("resume_path", "—")
                skills = c.get("skills", [])

                label_html = (
                    f"<span style='min-width:160px;display:inline-block;font-weight:600;'>{name}</span>"
                    f"<span style='min-width:180px;display:inline-block;color:#64748b;font-size:12px;'>{email}</span>"
                    f"{_skill_badges(skills, limit=4)}"
                )

                with st.expander(f"{name}  ·  {email}"):
                    d1, d2, d3 = st.columns([1, 2, 1])

                    with d1:
                        st.markdown("<div class='sh-section-heading'>Contact</div>", unsafe_allow_html=True)
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
        st.markdown("<div class='sh-page-subtitle' style='margin-bottom:14px;'>Enter the required skills for an open position to rank candidates by compatibility.</div>",
                    unsafe_allow_html=True)

        jc1, jc2 = st.columns([4, 1])
        with jc1:
            req_input = st.text_input(
                "Required skills",
                value="Python, Machine Learning, SQL",
                placeholder="e.g. Python, TensorFlow, SQL, Docker",
                label_visibility="collapsed",
            )
        with jc2:
            match_clicked = st.button("Match & Rank", type="primary", use_container_width=True)

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
                            name    = item.get("candidate_name", "Unknown")
                            email   = item.get("email", "—")
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
