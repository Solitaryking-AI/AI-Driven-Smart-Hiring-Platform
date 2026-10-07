import streamlit as st
import requests
import pandas as pd
import json
import os
import io
import wave
import hashlib
from typing import Any, Dict, List, Optional
import plotly.express as px
import plotly.graph_objects as go
from services import hiring_score as hiring_score_engine

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SmartHire AI | Enterprise ATS & Recruitment Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE_URL = "http://localhost:8000"
CANDIDATE_FETCH_LIMIT = 20000

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
if "theme" not in st.session_state:
    st.session_state["theme"] = "dark"

if "active_nav" not in st.session_state:
    st.session_state["active_nav"] = "Dashboard"

# ---------------------------------------------------------------------------
# Lucide-style Inline SVG Icon Helper
# ---------------------------------------------------------------------------
def render_svg(icon_name: str, size: int = 18, color: str = "currentColor") -> str:
    icons = {
        "dashboard": '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
        "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
        "briefcase": '<rect width="20" height="14" x="2" y="7" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
        "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
        "chat": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
        "analytics": '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
        "compass": '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
        "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
        "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
        "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
        "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
        "check": '<polyline points="20 6 9 17 4 12"/>',
        "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
        "filter": '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
        "log-out": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
        "sparkles": '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/>',
        "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
        "trash": '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
        "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
        "mic": '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/>',
        "volume": '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>',
        "mail": '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
        "phone": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
        "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
        "award": '<circle cx="12" cy="8" r="6"/><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"/>',
    }
    inner = icons.get(icon_name, '<circle cx="12" cy="12" r="10"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:middle;">{inner}</svg>'''

# ---------------------------------------------------------------------------
# Plotly Theme Layout Helper
# ---------------------------------------------------------------------------
def get_plotly_layout(theme: str = "dark"):
    is_dark = (theme == "dark")
    font_color = "#F8FAFC" if is_dark else "#0F172A"
    grid_color = "rgba(255,255,255,0.08)" if is_dark else "rgba(15, 23, 42, 0.06)"
    bg_color = "rgba(0,0,0,0)"
    return {
        "template": "plotly_dark" if is_dark else "plotly_white",
        "plot_bgcolor": bg_color,
        "paper_bgcolor": bg_color,
        "font": dict(family="Inter", color=font_color, size=12),
        "gridcolor": grid_color,
    }

def _theme_primary() -> str:
    return "#6366F1" if st.session_state.get("theme", "dark") == "dark" else "#2563EB"

def _mic_neutral_color() -> str:
    return "#4F46E5" if st.session_state.get("theme", "dark") == "dark" else "#2563EB"


# ---------------------------------------------------------------------------
# Centralized Design System & CSS Engine (Dual Theme Support)
# ---------------------------------------------------------------------------
def load_css():
    theme = st.session_state.get("theme", "dark")
    is_dark = (theme == "dark")

    if is_dark:
        bg_app        = "#0B1120"
        bg_card       = "#111827"
        bg_card_sub   = "#1A2234"
        bg_input      = "#0F172A"
        bg_sidebar    = "#0E1526"
        border_col    = "rgba(255, 255, 255, 0.08)"
        border_hover  = "rgba(255, 255, 255, 0.16)"
        border_light  = "rgba(255, 255, 255, 0.05)"
        text_primary  = "#F8FAFC"
        text_muted    = "#94A3B8"
        text_subtle   = "#64748B"
        primary_col   = "#6366F1"
        primary_hover = "#4F46E5"
        primary_tint  = "rgba(99, 102, 241, 0.14)"
        shadow_card   = "0 1px 3px rgba(0, 0, 0, 0.35), 0 1px 2px rgba(0, 0, 0, 0.24)"
        avatar_bg     = "linear-gradient(135deg, #6366F1, #818CF8)"
        success_bg    = "rgba(16, 185, 129, 0.15)"
        success_text  = "#10B981"
        warning_bg    = "rgba(245, 158, 11, 0.15)"
        warning_text  = "#F59E0B"
        danger_bg     = "rgba(244, 63, 94, 0.15)"
        danger_text   = "#F43F5E"
    else:
        bg_app        = "#F6F8FC"
        bg_card       = "#FFFFFF"
        bg_card_sub   = "#F1F5F9"
        bg_input      = "#FFFFFF"
        bg_sidebar    = "#FFFFFF"
        border_col    = "#D9E1EC"
        border_hover  = "#CBD5E1"
        border_light  = "#E7ECF3"
        text_primary  = "#0F172A"
        text_muted    = "#475569"
        text_subtle   = "#64748B"
        primary_col   = "#2563EB"
        primary_hover = "#1D4ED8"
        primary_tint  = "#EFF6FF"
        shadow_card   = "0 1px 3px rgba(15, 23, 42, 0.05), 0 1px 2px rgba(15, 23, 42, 0.03)"
        avatar_bg     = "linear-gradient(135deg, #2563EB, #3B82F6)"
        success_bg    = "#ECFDF5"
        success_text  = "#059669"
        warning_bg    = "#FFFBEB"
        warning_text  = "#D97706"
        danger_bg     = "#FEF2F2"
        danger_text   = "#DC2626"

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    *, *::before, *::after {{ box-sizing: border-box; }}

    :root {{
        --background:        {bg_app};
        --surface:           {bg_card};
        --surface-secondary: {bg_card_sub};
        --bg-app:            {bg_app};
        --bg-card:           {bg_card};
        --bg-card-sub:       {bg_card_sub};
        --bg-input:          {bg_input};
        --bg-sidebar:        {bg_sidebar};
        --border:            {border_col};
        --border-hover:      {border_hover};
        --border-light:      {border_light};
        --text-primary:      {text_primary};
        --text-secondary:    {text_muted};
        --text-muted:        {text_subtle};
        --text-subtle:       {text_subtle};
        --primary:           {primary_col};
        --primary-hover:     {primary_hover};
        --primary-light:     {primary_tint};
        --primary-tint:      {primary_tint};
        --shadow-card:       {shadow_card};
        --radius:            10px;
        --radius-sm:         6px;
        --avatar-bg:         {avatar_bg};
        --success:           #10B981;
        --success-light:     {success_bg};
        --success-text:      {success_text};
        --warning:           #F59E0B;
        --warning-light:     {warning_bg};
        --warning-text:      {warning_text};
        --danger:            #EF4444;
        --danger-light:      {danger_bg};
        --danger-text:       {danger_text};
    }}

    html, body, .stApp {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background-color: var(--background) !important;
        color: var(--text-primary) !important;
        font-size: 14px;
        line-height: 1.5;
    }}

    .stApp > header {{ background: transparent !important; border-bottom: 1px solid var(--border) !important; }}
    [data-testid="stSidebar"] {{
        background: var(--bg-sidebar) !important;
        border-right: 1px solid var(--border) !important;
        width: 250px !important;
    }}
    [data-testid="stSidebarNav"] {{ display: none !important; }}
    .block-container {{
        padding: 24px 32px 48px !important;
        max-width: 1360px !important;
    }}

    @media (max-width: 768px) {{
        .block-container {{ padding: 16px 14px 32px !important; }}
    }}

    h1, h2, h3, h4, h5, h6 {{
        color: var(--text-primary) !important;
        font-weight: 600;
        margin: 0 0 6px;
        letter-spacing: -0.02em;
    }}
    p, span, li, label {{ color: var(--text-primary); }}

    .sh-topbar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 16px;
        margin-bottom: 20px;
        border-bottom: 1px solid var(--border);
    }}
    .sh-breadcrumb {{
        font-size: 12px;
        font-weight: 500;
        color: var(--text-secondary);
        display: flex;
        align-items: center;
        gap: 6px;
    }}
    .sh-breadcrumb strong {{ color: var(--text-primary); }}

    .sh-page-header {{
        margin-bottom: 24px;
    }}
    .sh-title {{
        font-size: 24px;
        font-weight: 700;
        color: var(--text-primary) !important;
        letter-spacing: -0.03em;
        line-height: 1.25;
        margin: 0;
    }}
    .sh-subtitle {{
        font-size: 13px;
        color: var(--text-secondary) !important;
        margin-top: 4px;
    }}

    .sh-card {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 20px 22px;
        box-shadow: var(--shadow-card);
        margin-bottom: 16px;
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }}
    .sh-card:hover {{
        border-color: var(--border-hover);
    }}
    .sh-card-sm {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
        padding: 14px 16px;
        margin-bottom: 12px;
    }}

    .sh-stat-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 16px;
        margin-bottom: 24px;
    }}
    .sh-stat-card {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 18px 20px;
        box-shadow: var(--shadow-card);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }}
    .sh-stat-top {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }}
    .sh-stat-label {{
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-secondary);
    }}
    .sh-stat-value {{
        font-size: 28px;
        font-weight: 700;
        color: var(--text-primary) !important;
        line-height: 1.2;
        letter-spacing: -0.02em;
    }}
    .sh-stat-pill {{
        font-size: 11px;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }}
    .sh-stat-pill-success {{ background: var(--success-light); color: var(--success-text); }}
    .sh-stat-pill-info    {{ background: var(--primary-light); color: var(--primary); }}
    .sh-stat-pill-warning {{ background: var(--warning-light); color: var(--warning-text); }}
    .sh-stat-pill-danger  {{ background: var(--danger-light); color: var(--danger-text); }}
    .sh-stat-pill-neutral {{ background: var(--surface-secondary); color: var(--text-secondary); }}

    .sh-nav-group-label {{
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-muted);
        padding: 14px 12px 6px;
    }}
    .sh-brand-box {{
        padding: 16px 14px 14px;
        border-bottom: 1px solid var(--border);
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .sh-brand-title {{
        font-size: 15px;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.02em;
        line-height: 1.2;
    }}
    .sh-brand-badge {{
        font-size: 10px;
        font-weight: 700;
        padding: 1px 6px;
        border-radius: 4px;
        background: var(--primary-light);
        color: var(--primary);
    }}

    [data-testid="stSidebar"] .stButton > button {{
        background: transparent !important;
        border: 1px solid transparent !important;
        color: var(--text-secondary) !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 7px 12px !important;
        height: 36px !important;
        text-align: left !important;
        width: 100% !important;
        border-radius: var(--radius-sm) !important;
        justify-content: flex-start !important;
        transition: all 0.12s ease !important;
    }}
    [data-testid="stSidebar"] .stButton > button:hover {{
        background: var(--surface-secondary) !important;
        color: var(--text-primary) !important;
    }}
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {{
        background: var(--primary-light) !important;
        color: var(--primary) !important;
        border-left: 3px solid var(--primary) !important;
        font-weight: 600 !important;
    }}

    .stButton > button {{
        background: var(--primary) !important;
        color: #ffffff !important;
        border: 1px solid var(--primary) !important;
        border-radius: var(--radius-sm) !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 7px 16px !important;
        height: 36px !important;
        transition: background 0.15s ease, border-color 0.15s ease, transform 0.05s ease !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.06) !important;
    }}
    .stButton > button:hover {{
        background: var(--primary-hover) !important;
        border-color: var(--primary-hover) !important;
    }}
    .stButton > button[kind="secondary"] {{
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        color: var(--text-primary) !important;
    }}
    .stButton > button[kind="secondary"]:hover {{
        border-color: var(--border-hover) !important;
        background: var(--surface-secondary) !important;
    }}

    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        background-color: transparent !important;
        border-bottom: 1px solid var(--border) !important;
        padding-bottom: 0px !important;
    }}
    .stTabs [data-baseweb="tab"] {{
        height: 38px !important;
        white-space: pre-wrap !important;
        background-color: transparent !important;
        border-radius: 6px 6px 0 0 !important;
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
        font-size: 13px !important;
        padding: 8px 16px !important;
        border: none !important;
        transition: color 0.15s ease, background 0.15s ease !important;
    }}
    .stTabs [data-baseweb="tab"]:hover {{
        color: var(--primary) !important;
        background-color: var(--primary-light) !important;
    }}
    .stTabs [aria-selected="true"] {{
        color: var(--primary) !important;
        font-weight: 600 !important;
        border-bottom: 2px solid var(--primary) !important;
    }}
    .stTabs [data-baseweb="tab-highlight"] {{
        background-color: var(--primary) !important;
    }}

    .stTextInput input, .stTextArea textarea, .stSelectbox select, [data-baseweb="select"] {{
        background: var(--bg-input) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
        color: var(--text-primary) !important;
        font-size: 13px !important;
    }}
    .stTextInput input:focus, .stTextArea textarea:focus {{
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 3px var(--primary-light) !important;
    }}
    [data-baseweb="select"] > div {{
        background: var(--bg-input) !important;
        border-color: var(--border) !important;
        color: var(--text-primary) !important;
    }}
    [data-baseweb="select"] > div:focus-within {{
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 3px var(--primary-light) !important;
    }}
    [data-baseweb="popover"], [data-baseweb="menu"] {{
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
    }}
    label {{
        font-size: 12px !important;
        font-weight: 500 !important;
        color: var(--text-secondary) !important;
        margin-bottom: 4px !important;
    }}

    [data-testid="stRadio"] label {{
        color: var(--text-primary) !important;
        font-size: 13px !important;
        font-weight: 500 !important;
    }}
    [data-testid="stRadio"] div[role="radiogroup"] > label:hover {{
        background-color: var(--surface-secondary) !important;
        border-radius: var(--radius-sm) !important;
    }}
    [data-testid="stRadio"] [aria-checked="true"] {{
        color: var(--primary) !important;
    }}
    [data-testid="stRadio"] [data-baseweb="radio"] input:checked + div {{
        border-color: var(--primary) !important;
        background-color: var(--primary) !important;
    }}

    .sh-badge {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 11px;
        font-weight: 500;
        padding: 2px 8px;
        border-radius: 4px;
        margin: 2px 4px 2px 0;
        line-height: 1.4;
    }}
    .sh-badge-primary  {{ background: var(--primary-light); color: var(--primary); }}
    .sh-badge-success  {{ background: var(--success-light); color: var(--success-text); }}
    .sh-badge-warning  {{ background: var(--warning-light); color: var(--warning-text); }}
    .sh-badge-danger   {{ background: var(--danger-light);  color: var(--danger-text); }}
    .sh-badge-neutral  {{ background: var(--surface-secondary); color: var(--text-secondary); border: 1px solid var(--border); }}

    .sh-score-high {{
        display: inline-block; font-size: 12px; font-weight: 700; padding: 2px 8px;
        border-radius: 4px; background: var(--success-light); color: var(--success-text);
    }}
    .sh-score-mid {{
        display: inline-block; font-size: 12px; font-weight: 700; padding: 2px 8px;
        border-radius: 4px; background: var(--warning-light); color: var(--warning-text);
    }}
    .sh-score-low {{
        display: inline-block; font-size: 12px; font-weight: 700; padding: 2px 8px;
        border-radius: 4px; background: var(--danger-light); color: var(--danger-text);
    }}

    .sh-cand-card {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 14px 18px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 16px;
        box-shadow: var(--shadow-card);
        transition: border-color 0.15s ease;
    }}
    .sh-cand-card:hover {{
        border-color: var(--border-hover);
    }}
    .sh-avatar {{
        width: 38px;
        height: 38px;
        border-radius: 50%;
        background: var(--avatar-bg);
        color: #ffffff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 13px;
        flex-shrink: 0;
    }}

    .sh-drawer-header {{
        background: var(--surface-secondary);
        border: 1px solid var(--border);
        border-radius: var(--radius) var(--radius) 0 0;
        padding: 18px 22px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}
    .sh-drawer-body {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-top: none;
        border-radius: 0 0 var(--radius) var(--radius);
        padding: 22px;
        margin-bottom: 24px;
        box-shadow: var(--shadow-card);
    }}

    .sh-kanban-col {{
        background: var(--surface-secondary);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 14px;
        min-height: 480px;
    }}
    .sh-kanban-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--border);
    }}
    .sh-kanban-title {{
        font-size: 13px;
        font-weight: 600;
        color: var(--text-primary);
    }}
    .sh-kanban-badge {{
        font-size: 11px;
        font-weight: 700;
        padding: 1px 7px;
        border-radius: 999px;
        background: var(--border);
        color: var(--text-muted);
    }}

    .sh-progress-track {{
        width: 100%;
        height: 4px;
        background: var(--surface-secondary);
        border-radius: 99px;
        margin-top: 8px;
        overflow: hidden;
    }}
    .sh-progress-fill {{ height: 4px; border-radius: 99px; }}

    hr {{
        border: none !important;
        border-top: 1px solid var(--border) !important;
        margin: 16px 0 !important;
    }}

    [data-testid="stDecoration"] {{ display: none !important; }}
    footer {{ display: none !important; }}
    #MainMenu {{ display: none !important; }}
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# API Session & Connection Pooling
# ---------------------------------------------------------------------------
_HTTP_SESSION = requests.Session()
_http_adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=50, max_retries=1)
_HTTP_SESSION.mount("http://", _http_adapter)
_HTTP_SESSION.mount("https://", _http_adapter)

def api_request(method: str, endpoint: str, token: str = None, **kwargs):
    url = f"{API_BASE_URL}{endpoint}"
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = _HTTP_SESSION.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 401:
            if endpoint in ("/api/auth/login", "/api/auth/register"):
                try:
                    detail = resp.json().get("detail", "Incorrect email or password.")
                except Exception:
                    detail = "Incorrect email or password."
                return {"error": detail}
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
        return {"error": "Cannot connect to backend. Make sure FastAPI is running on http://localhost:8000"}
    except Exception as e:
        return {"error": str(e)}

def _handle_unauthorized(res: dict):
    if isinstance(res, dict) and res.get("__unauthorized"):
        st.session_state["session_expired_message"] = "Session expired. Please log in again."
        for key in ("auth_token", "user"):
            st.session_state.pop(key, None)
        for key in (
            "cand_active_mock_id",
            "active_interview_session_id",
            "practice_feedback_cache",
            "latest_resume_analysis",
            "quick_match_res",
            "selected_candidate_id",
        ):
            st.session_state.pop(key, None)
        st.rerun()

# ---------------------------------------------------------------------------
# Data Caching & Strict Deduplication Helpers
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def get_cached_candidates(token: str, limit: int):
    candidates_res = api_request(
        "GET", "/api/candidates", token=token,
        params={"limit": limit},
    )
    candidates = []
    if not (isinstance(candidates_res, dict) and "error" in candidates_res):
        candidates = (candidates_res.get("candidates", [])
                      if isinstance(candidates_res, dict) else candidates_res)
        if not isinstance(candidates, list):
            candidates = []

    seen_ids = set()
    seen_identities = set()
    deduped = []
    for c in candidates:
        cid = c.get("candidate_id")
        name_str = str(c.get("name", "")).strip().lower()
        email_str = str(c.get("email", "")).strip().lower()
        ident = (name_str, email_str)

        if cid is not None and cid in seen_ids:
            continue
        if name_str and email_str and ident in seen_identities:
            continue
        if cid is not None:
            seen_ids.add(cid)
        if name_str and email_str:
            seen_identities.add(ident)
        deduped.append(c)

    candidates = deduped
    for c in candidates:
        if "hiring_score" not in c:
            c["hiring_score"] = hiring_score_engine.calculate_hiring_score(c)["hiring_score"]

    all_skills = [s for c in candidates for s in c.get("skills", [])]
    return candidates_res, candidates, all_skills

@st.cache_data(ttl=60, show_spinner=False)
def get_cached_analytics_summary(token: str):
    return api_request("GET", "/api/analytics/summary", token=token)

@st.cache_data(ttl=60, show_spinner=False)
def get_cached_jobs(token: str):
    jobs_res = api_request("GET", "/api/jobs", token=token)
    return jobs_res if isinstance(jobs_res, list) else []

@st.cache_data(ttl=60, show_spinner=False)
def get_cached_analytics_skills(token: str):
    return api_request("GET", "/api/analytics/skills", token=token)

@st.cache_data(ttl=60, show_spinner=False)
def get_cached_skill_gap_report(job_id: int, token: str):
    return api_request("GET", f"/api/jobs/{job_id}/skill-gap-report", token=token)

@st.cache_data(ttl=60, show_spinner=False)
def get_cached_candidate_gap(job_id: int, cid: int, token: str):
    return api_request("GET", f"/api/jobs/{job_id}/skill-gap-report/candidates/{cid}", token=token)

@st.cache_data(ttl=60, show_spinner=False)
def get_cached_candidate_development_report(job_id: int, cid: int, token: str):
    return api_request("GET", f"/api/jobs/{job_id}/skill-gap-report/candidates/{cid}/development-report", token=token)

def invalidate_candidate_caches():
    get_cached_candidates.clear()
    get_cached_analytics_summary.clear()
    get_cached_analytics_skills.clear()
    get_cached_skill_gap_report.clear()
    get_cached_candidate_gap.clear()
    get_cached_candidate_development_report.clear()

def invalidate_job_caches():
    get_cached_jobs.clear()
    get_cached_skill_gap_report.clear()
    get_cached_candidate_gap.clear()
    get_cached_candidate_development_report.clear()

# ---------------------------------------------------------------------------
# Formatting, Voice & Scoring Helpers
# ---------------------------------------------------------------------------
ROLES = ["Candidate", "Recruiter", "HR Manager", "Admin"]
_TTS_CACHE: Dict[str, bytes] = {}

def _text_to_speech_bytes(text: str) -> bytes | None:
    if not text or not text.strip():
        return None
    cache_key = hashlib.md5(text.strip().encode("utf-8")).hexdigest()
    if cache_key in _TTS_CACHE:
        return _TTS_CACHE[cache_key]
    try:
        import pyttsx3
        import tempfile
        engine = pyttsx3.init()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        if audio_bytes:
            if len(_TTS_CACHE) > 100:
                _TTS_CACHE.clear()
            _TTS_CACHE[cache_key] = audio_bytes
        return audio_bytes
    except Exception:
        return None

def _speech_to_text(audio_bytes: bytes) -> str | None:
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        recognizer.operation_timeout = 10
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio_data = recognizer.record(source)
        return recognizer.recognize_google(audio_data)
    except Exception:
        return None

def _display_name(name: Any, default: str = "Unknown Candidate") -> str:
    if not name or str(name).strip().lower() in ("none", "null", "nan", ""):
        return default
    return str(name).strip()

def _display_email(email: Any, default: str = "—") -> str:
    if not email or str(email).strip().lower() in ("none", "null", "nan", ""):
        return default
    return str(email).strip()

def _get_avatar_initials(name: str) -> str:
    parts = name.strip().split()
    if not parts or parts[0] == "Unknown":
        return "C"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()

def _score_badge(score: float) -> str:
    cls = "sh-score-high" if score >= 70 else "sh-score-mid" if score >= 40 else "sh-score-low"
    return f"<span class='{cls}'>{score:.0f}%</span>"

def _hiring_score_badge(score: float) -> str:
    cls = "sh-score-high" if score >= 75 else "sh-score-mid" if score >= 55 else "sh-score-low"
    return f"<span class='{cls}'>Hiring Score: {score:.0f}%</span>"

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

def _safe_fetch_file(url: str, token: str, timeout: int = 15) -> Optional[bytes]:
    try:
        r = _HTTP_SESSION.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=timeout)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    return None

# ---------------------------------------------------------------------------
# Topbar Component
# ---------------------------------------------------------------------------
def render_recruiter_topbar(breadcrumb: str, title: str, subtitle: str):
    st.markdown(f"""
    <div class='sh-topbar'>
        <div class='sh-breadcrumb'>
            {render_svg('sparkles', 14, _theme_primary())}
            <span>SmartHire AI</span>
            <span>/</span>
            <strong>{breadcrumb}</strong>
        </div>
        <div style='display:flex;align-items:center;gap:12px;'>
            <span class='sh-stat-pill sh-stat-pill-info'>Production ATS v2.4</span>
        </div>
    </div>
    <div class='sh-page-header'>
        <h1 class='sh-title'>{title}</h1>
        <div class='sh-subtitle'>{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Candidate Detail Drawer Component
# ---------------------------------------------------------------------------
def show_candidate_drawer(candidate: dict, jobs_list: list, token: str):
    cid = candidate.get("candidate_id")
    name = _display_name(candidate.get("name"))
    email = _display_email(candidate.get("email"))
    phone = candidate.get("phone") or "Not provided"
    hs = candidate.get("hiring_score", 0.0)
    resume_file = candidate.get("resume_path") or "Direct Submission"
    skills = candidate.get("skills", [])
    exp_list = candidate.get("experience", [])
    edu_list = candidate.get("education", [])

    st.markdown(f"""
    <div class='sh-drawer-header'>
        <div style='display:flex;align-items:center;gap:14px;'>
            <div class='sh-avatar'>{_get_avatar_initials(name)}</div>
            <div>
                <div style='font-size:17px;font-weight:700;color:var(--text-primary);'>{name}</div>
                <div style='font-size:12px;color:var(--text-muted);'>{email} · {phone}</div>
            </div>
        </div>
        <div>
            {_hiring_score_badge(hs)}
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown("<div class='sh-drawer-body'>", unsafe_allow_html=True)

        d_col1, d_col2 = st.columns([1.5, 1])
        with d_col1:
            st.markdown("<h4 style='font-size:14px;margin-bottom:8px;'>5-Pillar AI Hiring Assessment</h4>", unsafe_allow_html=True)
            breakdown = hiring_score_engine.calculate_hiring_score(candidate).get("component_scores", {})
            for comp, score_val in breakdown.items():
                comp_title = comp.replace("_", " ").title()
                st.markdown(f"""
                <div style='display:flex;justify-content:space-between;font-size:12px;color:var(--text-muted);margin-bottom:2px;'>
                    <span>{comp_title}</span>
                    <span style='font-weight:600;color:var(--text-primary);'>{score_val:.0f}%</span>
                </div>
                """, unsafe_allow_html=True)
                st.progress(score_val / 100.0)

            st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
            st.markdown("<h4 style='font-size:14px;margin-bottom:8px;'>Extracted Technical Skills</h4>", unsafe_allow_html=True)
            if skills:
                st.markdown(_skill_badges(skills, "primary"), unsafe_allow_html=True)
            else:
                st.caption("No technical skills detected.")

        with d_col2:
            st.markdown("<h4 style='font-size:14px;margin-bottom:8px;'>Candidate Profile Meta</h4>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class='sh-card-sm' style='margin-bottom:12px;'>
                <div style='font-size:11px;color:var(--text-subtle);text-transform:uppercase;'>Resume Source</div>
                <div style='font-size:13px;font-weight:500;margin-top:2px;'>{resume_file}</div>
                <div style='font-size:11px;color:var(--text-subtle);text-transform:uppercase;margin-top:10px;'>Candidate ID</div>
                <div style='font-size:13px;font-weight:500;margin-top:2px;'>#{cid}</div>
            </div>
            """, unsafe_allow_html=True)

            action_c1, action_c2 = st.columns(2)
            with action_c1:
                if st.button("Close Profile", key="btn_close_drawer", use_container_width=True, type="secondary"):
                    st.session_state.pop("selected_candidate_id", None)
                    st.rerun()
            with action_c2:
                if st.button("Delete Candidate", key=f"btn_drawer_del_{cid}", use_container_width=True):
                    dr = api_request("DELETE", f"/api/candidates/{cid}", token=token)
                    _handle_unauthorized(dr)
                    if "error" in dr:
                        st.error(dr["error"])
                    else:
                        invalidate_candidate_caches()
                        st.session_state.pop("selected_candidate_id", None)
                        st.success("Candidate removed from pool.")
                        st.rerun()

        dt1, dt2, dt3 = st.tabs(["Experience Timeline", "Education & Credentials", "Match with Active Positions"])
        with dt1:
            if exp_list:
                for exp in exp_list:
                    raw = exp.get("raw", exp) if isinstance(exp, dict) else str(exp)
                    dates = exp.get("dates", "") if isinstance(exp, dict) else ""
                    st.markdown(f"""
                    <div style='padding:8px 0;border-bottom:1px solid var(--border);'>
                        <div style='font-size:13px;font-weight:600;'>{raw}</div>
                        <div style='font-size:11px;color:var(--text-subtle);'>{dates}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.caption("No experience records extracted.")

        with dt2:
            if edu_list:
                for edu in edu_list:
                    raw = edu.get("raw", edu) if isinstance(edu, dict) else str(edu)
                    st.markdown(f"<div style='font-size:13px;padding:6px 0;'>🎓 {raw}</div>", unsafe_allow_html=True)
            else:
                st.caption("No education records extracted.")

        with dt3:
            if not jobs_list:
                st.caption("No active job postings to match.")
            else:
                for j in jobs_list[:5]:
                    req_skills = j.get("required_skills", [])
                    matched = [s for s in skills if any(s.lower() == req.lower() for req in req_skills)]
                    ratio = len(matched) / len(req_skills) * 100 if req_skills else 0
                    st.markdown(f"""
                    <div style='display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border);'>
                        <div>
                            <div style='font-size:13px;font-weight:600;'>{j.get('title')}</div>
                            <div style='font-size:11px;color:var(--text-subtle);'>{j.get('department') or 'General'} · Match: {len(matched)}/{len(req_skills)} required skills</div>
                        </div>
                        <div>{_score_badge(ratio)}</div>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# VIEW: Executive Overview (Dashboard)
# ---------------------------------------------------------------------------
def show_dashboard_overview(candidates, jobs_list, summary_res, all_skills_flat, token):
    render_recruiter_topbar(
        "Overview",
        "Executive Recruitment Overview",
        "Monitor real-time candidate pool health, active hiring pipelines, and key ATS performance metrics."
    )

    if isinstance(summary_res, dict) and "error" not in summary_res:
        total_candidates = summary_res.get("total_candidates", len(candidates))
        unique_skills    = summary_res.get("unique_skills", len(set(all_skills_flat)))
        avg_skills       = summary_res.get("avg_skills_per_candidate", 0)
    else:
        total_candidates = len(candidates)
        unique_skills    = len(set(all_skills_flat))
        avg_skills       = round(len(all_skills_flat) / total_candidates, 1) if total_candidates else 0

    active_jobs_count = len(jobs_list)

    st.markdown(f"""
    <div class='sh-stat-grid'>
        <div class='sh-stat-card'>
            <div class='sh-stat-top'>
                <span class='sh-stat-label'>Total Candidates</span>
                <span class='sh-stat-pill sh-stat-pill-info'>{render_svg('users', 12, _theme_primary())} Active Pool</span>
            </div>
            <div class='sh-stat-value'>{total_candidates}</div>
        </div>
        <div class='sh-stat-card'>
            <div class='sh-stat-top'>
                <span class='sh-stat-label'>Active Positions</span>
                <span class='sh-stat-pill sh-stat-pill-success'>{render_svg('briefcase', 12, '#10B981')} Open</span>
            </div>
            <div class='sh-stat-value'>{active_jobs_count}</div>
        </div>
        <div class='sh-stat-card'>
            <div class='sh-stat-top'>
                <span class='sh-stat-label'>Unique Skills</span>
                <span class='sh-stat-pill sh-stat-pill-neutral'>Breadth</span>
            </div>
            <div class='sh-stat-value'>{unique_skills}</div>
        </div>
        <div class='sh-stat-card'>
            <div class='sh-stat-top'>
                <span class='sh-stat-label'>Avg Skills / Profile</span>
                <span class='sh-stat-pill sh-stat-pill-neutral'>{avg_skills} avg</span>
            </div>
            <div class='sh-stat-value'>{avg_skills}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_funnel, col_recent = st.columns([1.2, 1])
    with col_funnel:
        st.markdown("<h3 style='font-size:16px;margin-bottom:4px;'>Hiring Funnel Status</h3>", unsafe_allow_html=True)
        st.caption("Visual representation of candidates transitioning through ATS stages.")

        funnel_stages = [
            ("Sourced & Parsed", total_candidates, 100),
            ("Profile Screened", int(total_candidates * 0.72) if total_candidates else 0, 72),
            ("Interview Scheduled", int(total_candidates * 0.38) if total_candidates else 0, 38),
            ("Final Evaluation", int(total_candidates * 0.16) if total_candidates else 0, 16),
            ("Offers Extended", int(total_candidates * 0.05) if total_candidates else 0, 5),
        ]
        for name, count, pct in funnel_stages:
            st.markdown(f"""
            <div style='margin-bottom:12px;'>
                <div style='display:flex;justify-content:space-between;font-size:13px;margin-bottom:3px;'>
                    <span style='font-weight:600;'>{name}</span>
                    <span style='color:var(--text-muted);'>{count} candidates ({pct}%)</span>
                </div>
                <div class='sh-progress-track'>
                    <div class='sh-progress-fill' style='width:{pct}%;background:var(--primary);'></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_recent:
        st.markdown("<h3 style='font-size:16px;margin-bottom:4px;'>Top Qualified Profiles</h3>", unsafe_allow_html=True)
        st.caption("Highest scoring candidates in the active talent pool.")

        if not candidates:
            st.info("No candidates in the database. Use 'Resume Parser' to ingest resumes.")
        else:
            top_candidates = sorted(candidates, key=lambda c: c.get("hiring_score", 0), reverse=True)[:5]
            for c in top_candidates:
                c_name = _display_name(c.get("name"))
                c_score = c.get("hiring_score", 0.0)
                cid = c.get("candidate_id")

                row_col1, row_col2 = st.columns([3, 1])
                with row_col1:
                    st.markdown(f"""
                    <div style='display:flex;align-items:center;gap:10px;padding:4px 0;'>
                        <div class='sh-avatar' style='width:30px;height:30px;font-size:11px;'>{_get_avatar_initials(c_name)}</div>
                        <div>
                            <div style='font-size:13px;font-weight:600;'>{c_name}</div>
                            <div style='font-size:11px;color:var(--text-subtle);'>{len(c.get('skills', []))} skills · {_score_badge(c_score)}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                with row_col2:
                    if st.button("Inspect", key=f"dash_inspect_{cid}", use_container_width=True, type="secondary"):
                        st.session_state["selected_candidate_id"] = cid
                        st.session_state["active_nav"] = "Candidates"
                        st.rerun()

# ---------------------------------------------------------------------------
# VIEW: Candidates Directory
# ---------------------------------------------------------------------------
def show_candidates_view(candidates, total_candidates, all_skills_flat, jobs_list, candidates_res, token):
    render_recruiter_topbar(
        "Recruitment / Candidates",
        "Candidate Talent Directory",
        "Explore parsed talent profiles, evaluate multi-dimensional hiring scores, and inspect detailed resumes."
    )

    selected_cid = st.session_state.get("selected_candidate_id")
    if selected_cid:
        selected_cand = next((c for c in candidates if c.get("candidate_id") == selected_cid), None)
        if selected_cand:
            show_candidate_drawer(selected_cand, jobs_list, token)

    if not candidates:
        if isinstance(candidates_res, dict) and "error" in candidates_res:
            st.error(candidates_res["error"])
        else:
            st.info("No candidates in the database. Head over to the 'Resume Parser' tab to upload resumes.")
        return

    f_c1, f_c2, f_c3 = st.columns([2.5, 2, 1.2])
    with f_c1:
        search_q = st.text_input("Search", placeholder="Search by name, email, or resume file...", label_visibility="collapsed")
    with f_c2:
        skill_filter = st.multiselect("Skills Filter", sorted(set(all_skills_flat)), placeholder="Filter by required skills...", label_visibility="collapsed")
    with f_c3:
        sort_by = st.selectbox("Sort Order", ["Highest Score", "Name (A-Z)", "Recent"], label_visibility="collapsed")

    filtered = candidates
    if search_q:
        q = search_q.lower()
        filtered = [
            c for c in filtered if
            q in (_display_name(c.get("name"))).lower() or
            q in (_display_email(c.get("email"))).lower() or
            q in (c.get("resume_path") or "").lower()
        ]
    if skill_filter:
        filtered = [c for c in filtered if all(s in c.get("skills", []) for s in skill_filter)]

    if sort_by == "Highest Score":
        filtered = sorted(filtered, key=lambda x: x.get("hiring_score", 0.0), reverse=True)
    elif sort_by == "Name (A-Z)":
        filtered = sorted(filtered, key=lambda x: str(x.get("name", "")).lower())

    st.markdown(f"<div style='font-size:12px;color:var(--text-muted);margin:8px 0 16px;'>Showing <b>{len(filtered)}</b> of {total_candidates} candidates</div>", unsafe_allow_html=True)

    for c in filtered:
        cid = c.get("candidate_id")
        name = _display_name(c.get("name"))
        email = _display_email(c.get("email"))
        src = c.get("resume_path", "Direct")
        skills = c.get("skills", [])
        hs = c.get("hiring_score", 0.0)
        hs_badge = _score_badge(hs)

        c_col1, c_col2 = st.columns([4.5, 1.2])
        with c_col1:
            st.markdown(f"""
            <div class='sh-cand-card'>
                <div class='sh-avatar'>{_get_avatar_initials(name)}</div>
                <div style='flex:1;'>
                    <div style='display:flex;align-items:center;gap:10px;'>
                        <span style='font-size:14px;font-weight:600;color:var(--text-primary);'>{name}</span>
                        {hs_badge}
                    </div>
                    <div style='font-size:12px;color:var(--text-muted);margin:2px 0 6px;'>
                        {email} · <span style='color:var(--text-subtle);'>{src}</span>
                    </div>
                    <div>{_skill_badges(skills, "primary", limit=6)}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with c_col2:
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            if st.button("Inspect Profile", key=f"cand_inspect_{cid}", use_container_width=True, type="secondary"):
                st.session_state["selected_candidate_id"] = cid
                st.rerun()

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    st.markdown("<h4 style='font-size:14px;'>Export Talent Pool</h4>", unsafe_allow_html=True)
    ex1, ex2, _ = st.columns([1.2, 1.2, 3])
    df_exp = pd.DataFrame(filtered)
    for col in ["skills", "education", "experience", "certifications"]:
        if col in df_exp.columns:
            df_exp[col] = df_exp[col].apply(lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x)
    with ex1:
        st.download_button("Export as CSV", data=df_exp.to_csv(index=False).encode(),
                           file_name="candidates_export.csv", mime="text/csv", use_container_width=True)
    with ex2:
        st.download_button("Export as JSON", data=json.dumps(filtered, indent=2).encode(),
                           file_name="candidates_export.json", mime="application/json", use_container_width=True)

# ---------------------------------------------------------------------------
# VIEW: Jobs Management
# ---------------------------------------------------------------------------
def show_jobs_view(jobs_list, candidates, token):
    render_recruiter_topbar(
        "Recruitment / Jobs",
        "Job Positions & Requirements",
        "Define target positions, set mandatory skill criteria, and benchmark pool readiness."
    )

    with st.expander("＋ Post New Job Opening", expanded=len(jobs_list) == 0):
        with st.form("post_job_form", clear_on_submit=True):
            fc1, fc2 = st.columns(2)
            with fc1:
                title = st.text_input("Job Title *", placeholder="e.g. Senior Machine Learning Engineer")
                dept = st.text_input("Department", placeholder="e.g. AI Platform")
                loc = st.text_input("Location", placeholder="e.g. San Francisco, CA / Remote")
            with fc2:
                emp = st.selectbox("Employment Type", ["Full-time", "Contract", "Part-time", "Internship"])
                sen = st.selectbox("Seniority Tier", ["Junior", "Mid-Level", "Senior", "Lead", "Principal"])
                exp_yrs = st.number_input("Minimum Experience (Years)", min_value=0, max_value=30, value=3)

            req_skills = st.text_input("Required Skills (Comma-separated) *", placeholder="e.g. Python, PyTorch, Kubernetes")
            nice_skills = st.text_input("Nice-to-Have Skills (Comma-separated)", placeholder="e.g. Docker, AWS, FastAPI")
            desc = st.text_area("Job Description (Optional)", placeholder="Key responsibilities and technical expectations...")

            submitted = st.form_submit_button("Create Job Position", type="primary")
            if submitted:
                if not title.strip():
                    st.error("Job title is required.")
                elif not req_skills.strip():
                    st.error("At least one required skill is needed.")
                else:
                    payload = {
                        "title": title.strip(),
                        "department": dept.strip() or None,
                        "location": loc.strip() or None,
                        "employment_type": emp,
                        "seniority": sen,
                        "min_experience_years": int(exp_yrs),
                        "required_skills": [s.strip() for s in req_skills.split(",") if s.strip()],
                        "nice_to_have_skills": [s.strip() for s in nice_skills.split(",") if s.strip()],
                        "description": desc.strip() or None,
                    }
                    res = api_request("POST", "/api/jobs", token=token, json=payload)
                    _handle_unauthorized(res)
                    if "error" in res:
                        st.error(res["error"])
                    else:
                        invalidate_job_caches()
                        st.success(f"Job '{title}' created successfully!")
                        st.rerun()

    if not jobs_list:
        st.info("No job openings created yet. Create your first position using the form above.")
        return

    st.markdown(f"<div style='font-size:12px;color:var(--text-muted);margin:16px 0 12px;'>Showing <b>{len(jobs_list)}</b> active job positions</div>", unsafe_allow_html=True)

    for j in jobs_list:
        jid = j["job_id"]
        title = j.get("title")
        dept = j.get("department") or "General"
        loc = j.get("location") or "Remote"
        sen = j.get("seniority") or "Mid"
        min_exp = j.get("min_experience_years", 0)
        req_skills = j.get("required_skills", [])
        nice_skills = j.get("nice_to_have_skills", [])

        match_count = 0
        for c in candidates:
            c_skills = [s.lower() for s in c.get("skills", [])]
            if any(req.lower() in c_skills for req in req_skills):
                match_count += 1

        st.markdown(f"""
        <div class='sh-card'>
            <div style='display:flex;justify-content:space-between;align-items:flex-start;'>
                <div>
                    <h3 style='font-size:16px;margin-bottom:2px;'>{title}</h3>
                    <div style='font-size:12px;color:var(--text-muted);margin-bottom:10px;'>
                        {dept} · {loc} · <b>{sen}</b> ({min_exp}+ yrs exp)
                    </div>
                </div>
                <div style='text-align:right;'>
                    <span class='sh-stat-pill sh-stat-pill-info'>{match_count} candidate matches</span>
                </div>
            </div>
            <div style='margin-bottom:6px;'>
                <span style='font-size:11px;font-weight:600;color:var(--text-subtle);text-transform:uppercase;'>Required:</span>
                {_skill_badges(req_skills, 'primary')}
            </div>
            {f"<div><span style='font-size:11px;font-weight:600;color:var(--text-subtle);text-transform:uppercase;'>Nice-to-Have:</span> {_skill_badges(nice_skills, 'neutral')}</div>" if nice_skills else ""}
        </div>
        """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# VIEW: Job Matcher
# ---------------------------------------------------------------------------
def show_job_matcher_view(jobs_list, candidates, token):
    render_recruiter_topbar(
        "Recruitment / Matcher",
        "Multi-Factor Candidate Matcher",
        "Rank candidate fitness against structured job requisitions or ad-hoc technical skill queries."
    )

    mode = st.radio("Matching Mode", ["Match against saved job position", "Quick search (free-text skills)"],
                    horizontal=True, label_visibility="collapsed")
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    if mode == "Match against saved job position":
        if not jobs_list:
            st.info("No saved jobs available. Please create a position in the 'Jobs' tab.")
            return

        job_opts = {f"{j['title']} · {j.get('department') or 'General'} ({j.get('location') or 'Remote'})": j for j in jobs_list}
        selected_label = st.selectbox("Target Role", list(job_opts.keys()), label_visibility="collapsed")
        selected_job = job_opts[selected_label]
        jid = selected_job["job_id"]

        run_match = st.button("Calculate Job Fit & Rank Candidates", type="primary", use_container_width=True)

        if run_match:
            with st.spinner("Executing multi-factor ranking engine..."):
                res = api_request("POST", f"/api/jobs/{jid}/match", token=token)
            _handle_unauthorized(res)
            if isinstance(res, dict) and "error" in res:
                st.error(res["error"])
            else:
                st.session_state[f"job_match_{jid}"] = res if isinstance(res, list) else []

        saved_match = st.session_state.get(f"job_match_{jid}")
        if saved_match is not None:
            if not saved_match:
                st.info("No candidates evaluated in pool.")
            else:
                st.markdown(f"<div style='font-size:13px;color:var(--text-muted);margin:14px 0 10px;'>Ranked <b>{len(saved_match)}</b> candidates for <b>{selected_job['title']}</b>:</div>", unsafe_allow_html=True)
                cand_hs_map = {c.get("candidate_id"): c.get("hiring_score", 70.0) for c in candidates if c.get("candidate_id") is not None}

                for item in saved_match:
                    c_name = _display_name(item.get("candidate_name"))
                    c_email = _display_email(item.get("email"))
                    f_score = item.get("final_score", 0.0)
                    sk_score = item.get("skills_score", 0.0)
                    nth_score = item.get("nice_to_have_score", 0.0)
                    exp_fit = item.get("experience_fit_score", 0.0)
                    exp_yrs = item.get("candidate_experience_years", 0.0)

                    cid = item.get("candidate_id")
                    hs = cand_hs_map.get(cid, 70.0)
                    blended = hiring_score_engine.blend_with_job_match(hs, f_score, hiring_weight=0.35)

                    matched_req = _skill_badges(item.get("matched_required", []), "success")
                    missing_req = _skill_badges(item.get("missing_required", []), "danger")
                    matched_nth = _skill_badges(item.get("matched_nice_to_have", []), "primary")

                    st.markdown(f"""
                    <div class='sh-card'>
                        <div style='display:flex;justify-content:space-between;align-items:flex-start;'>
                            <div>
                                <h3 style='font-size:15px;margin-bottom:2px;'>{c_name}</h3>
                                <div style='font-size:12px;color:var(--text-muted);margin-bottom:6px;'>{c_email}</div>
                            </div>
                            <div style='text-align:right;'>
                                {_score_badge(blended)}
                                <div style='font-size:10px;color:var(--text-subtle);margin-top:2px;'>Blended Fit</div>
                            </div>
                        </div>
                        <div style='font-size:12px;color:var(--text-muted);margin-bottom:6px;'>
                            Job Fit: <b>{f_score:.0f}%</b> · Hiring Score: <b>{hs:.0f}%</b> · Required Match: <b>{sk_score:.0f}%</b> · Exp: <b>{exp_fit:.0f}%</b> (~{exp_yrs:.1f} yrs)
                        </div>
                        <div>{matched_req}{missing_req}{matched_nth}</div>
                        <div class='sh-progress-track'>
                            <div class='sh-progress-fill' style='width:{min(blended, 100):.0f}%;background:{_score_bar_color(blended)};'></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        qc1, qc2 = st.columns([3.5, 1])
        with qc1:
            req_input = st.text_input("Required Skills", placeholder="Type skills to match, e.g. Python, SQL, Docker...", label_visibility="collapsed")
        with qc2:
            q_match_btn = st.button("Rank Profiles", type="primary", use_container_width=True)

        if q_match_btn:
            if not req_input.strip():
                st.warning("Enter at least one skill keyword.")
            else:
                with st.spinner("Ranking candidates..."):
                    mr = api_request("POST", "/api/match", token=token, json={"required_skills": req_input.strip()})
                _handle_unauthorized(mr)
                if isinstance(mr, dict) and "error" in mr:
                    st.error(mr["error"])
                else:
                    st.session_state["quick_match_res"] = mr if isinstance(mr, list) else mr.get("results", [])

        saved_q = st.session_state.get("quick_match_res")
        if saved_q:
            for item in saved_q:
                c_name = _display_name(item.get("candidate_name"))
                c_email = _display_email(item.get("email"))
                score = item.get("match_score", 0)
                matched = _skill_badges(item.get("matched_skills", []), "success")
                missing = _skill_badges(item.get("missing_skills", []), "danger")

                st.markdown(f"""
                <div class='sh-card'>
                    <div style='display:flex;justify-content:space-between;align-items:flex-start;'>
                        <div>
                            <h3 style='font-size:15px;margin-bottom:2px;'>{c_name}</h3>
                            <div style='font-size:12px;color:var(--text-muted);margin-bottom:6px;'>{c_email}</div>
                            <div>{matched}{missing}</div>
                        </div>
                        <div>{_score_badge(score)}</div>
                    </div>
                    <div class='sh-progress-track'>
                        <div class='sh-progress-fill' style='width:{min(score, 100):.0f}%;background:{_score_bar_color(score)};'></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# VIEW: Talent Analytics & Skill Distribution
# ---------------------------------------------------------------------------
def show_analytics_view(candidates, total_candidates, token):
    render_recruiter_topbar(
        "Insights / Analytics",
        "Talent Pool Analytics & Distribution",
        "Analyze skill frequencies, talent clusters, and candidate competency distributions across the active pool."
    )

    ar = get_cached_analytics_skills(token)
    _handle_unauthorized(ar)

    if isinstance(ar, dict) and "error" in ar:
        st.warning(f"Could not load analytics: {ar['error']}")
        return

    skills_data = ar if isinstance(ar, list) else ar.get("skills_frequency", [])
    if not skills_data:
        st.info("No skill frequency data available yet. Please parse some resumes first.")
        return

    df_sk = pd.DataFrame(skills_data)
    if "skill" in df_sk.columns:
        df_sk.columns = [c.title() for c in df_sk.columns]
    df_sk = df_sk.sort_values("Count", ascending=False).reset_index(drop=True)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f"""
        <div class='sh-stat-card'>
            <div class='sh-stat-label'>Unique Skills Identified</div>
            <div class='sh-stat-value'>{len(df_sk)}</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        top_skill = df_sk.iloc[0]["Skill"] if not df_sk.empty else "—"
        st.markdown(f"""
        <div class='sh-stat-card'>
            <div class='sh-stat-label'>Top Recurring Skill</div>
            <div class='sh-stat-value' style='font-size:22px;color:var(--primary);'>{top_skill}</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        total_occur = int(df_sk["Count"].sum()) if not df_sk.empty else 0
        st.markdown(f"""
        <div class='sh-stat-card'>
            <div class='sh-stat-label'>Total Skill Mentions</div>
            <div class='sh-stat-value'>{total_occur}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    ch1, ch2 = st.columns([1.6, 1.2])
    layout_theme = get_plotly_layout(st.session_state.get("theme", "dark"))
    is_cur_dark = (st.session_state.get("theme", "dark") == "dark")
    bar_scale = [[0, "#4F46E5"], [1, "#818CF8"]] if is_cur_dark else [[0, "#1D4ED8"], [1, "#3B82F6"]]
    with ch1:
        st.markdown("<h3 style='font-size:15px;margin-bottom:4px;'>Top 20 Skills by Frequency</h3>", unsafe_allow_html=True)
        top20 = df_sk.head(20)
        fig_bar = px.bar(
            top20, x="Count", y="Skill", orientation="h",
            color="Count",
            color_continuous_scale=bar_scale,
        )
        fig_bar.update_layout(
            template=layout_theme["template"],
            plot_bgcolor=layout_theme["plot_bgcolor"],
            paper_bgcolor=layout_theme["paper_bgcolor"],
            font=layout_theme["font"],
            yaxis={"categoryorder": "total ascending"},
            margin=dict(l=0, r=0, t=10, b=0),
            showlegend=False,
            coloraxis_showscale=False,
            height=380,
        )
        fig_bar.update_traces(marker_line_width=0)
        st.plotly_chart(fig_bar, use_container_width=True)

    with ch2:
        st.markdown("<h3 style='font-size:15px;margin-bottom:4px;'>Top 10 Skill Share</h3>", unsafe_allow_html=True)
        top10 = df_sk.head(10)
        pie_colors = (
            [
                "#4F46E5", "#6366f1", "#818cf8", "#a5b4fc",
                "#312e81", "#3730a3", "#4338CA", "#6d28d9",
                "#7c3aed", "#8b5cf6",
            ]
            if is_cur_dark
            else [
                "#1D4ED8", "#2563EB", "#3B82F6", "#60A5FA", "#93C5FD",
                "#0284C7", "#0EA5E9", "#38BDF8", "#475569", "#64748B",
            ]
        )
        fig_pie = px.pie(
            top10, values="Count", names="Skill", hole=0.5,
            color_discrete_sequence=pie_colors,
        )
        fig_pie.update_layout(
            template=layout_theme["template"],
            plot_bgcolor=layout_theme["plot_bgcolor"],
            paper_bgcolor=layout_theme["paper_bgcolor"],
            font=layout_theme["font"],
            margin=dict(l=0, r=0, t=10, b=0),
            height=380,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("<h3 style='font-size:15px;margin-bottom:8px;'>Skill Frequency Distribution Table</h3>", unsafe_allow_html=True)
    st.dataframe(df_sk, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# VIEW: Skill Gap Analysis & Executive Reports
# ---------------------------------------------------------------------------
def show_skill_gap_view(jobs_list, candidates, token):
    render_recruiter_topbar(
        "Insights / Skill Gap",
        "Pool Readiness & Skill Deficiencies",
        "Detect talent pool bottlenecks, identify missing core competencies, and export executive reports."
    )

    if not jobs_list:
        st.info("No job openings found. Please create a position in the 'Jobs' tab.")
        return

    job_map = {f"{j['title']} ({j.get('department') or 'General'})": j for j in jobs_list}
    selected_label = st.selectbox("Select Target Job Opening", list(job_map.keys()))
    selected_job = job_map[selected_label]
    jid = selected_job["job_id"]

    report_res = get_cached_skill_gap_report(jid, token)
    _handle_unauthorized(report_res)

    if isinstance(report_res, dict) and "error" in report_res:
        st.error(report_res["error"])
        return

    report = report_res
    readiness = report.get("pool_readiness_score", 0.0)
    analyzed_count = report.get("total_candidates_analyzed", 0)
    crit_gaps = report.get("critical_gaps", [])
    mod_gaps = report.get("moderate_gaps", [])
    min_gaps = report.get("minor_gaps", [])
    well_cov = report.get("well_covered_skills", [])

    st.markdown(f"""
    <div class='sh-stat-grid'>
        <div class='sh-stat-card'>
            <div class='sh-stat-top'>
                <span class='sh-stat-label'>Pool Readiness</span>
                <span class='sh-stat-pill sh-stat-pill-info'>Score</span>
            </div>
            <div class='sh-stat-value' style='color:{_score_bar_color(readiness)};'>{readiness:.1f}%</div>
        </div>
        <div class='sh-stat-card'>
            <div class='sh-stat-top'>
                <span class='sh-stat-label'>Candidates Evaluated</span>
                <span class='sh-stat-pill sh-stat-pill-neutral'>Total</span>
            </div>
            <div class='sh-stat-value'>{analyzed_count}</div>
        </div>
        <div class='sh-stat-card'>
            <div class='sh-stat-top'>
                <span class='sh-stat-label'>Critical Gaps (≥50%)</span>
                <span class='sh-stat-pill sh-stat-pill-danger'>High Risk</span>
            </div>
            <div class='sh-stat-value' style='color:var(--danger-text);'>{len(crit_gaps)}</div>
        </div>
        <div class='sh-stat-card'>
            <div class='sh-stat-top'>
                <span class='sh-stat-label'>Moderate Gaps</span>
                <span class='sh-stat-pill sh-stat-pill-warning'>Medium</span>
            </div>
            <div class='sh-stat-value' style='color:var(--warning-text);'>{len(mod_gaps)}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    all_gaps = crit_gaps + mod_gaps + min_gaps
    if all_gaps:
        st.markdown("<h3 style='font-size:16px;margin-bottom:4px;'>Skill Deficiencies Breakdown</h3>", unsafe_allow_html=True)
        st.caption("Percentage of candidate pool currently lacking required skills.")

        df_gaps = pd.DataFrame(all_gaps)
        df_gaps["severity"] = df_gaps["severity"].str.capitalize()
        df_gaps = df_gaps.sort_values("missing_percentage", ascending=True)

        layout_theme = get_plotly_layout(st.session_state.get("theme", "dark"))
        is_cur_dark = (st.session_state.get("theme", "dark") == "dark")
        minor_color = "#6366F1" if is_cur_dark else "#2563EB"
        fig_gaps = px.bar(
            df_gaps,
            x="missing_percentage",
            y="skill",
            color="severity",
            orientation="h",
            color_discrete_map={"Critical": "#F43F5E", "Moderate": "#F59E0B", "Minor": minor_color},
            labels={"missing_percentage": "Pool Missing (%)", "skill": "Skill"},
        )
        fig_gaps.update_layout(
            template=layout_theme["template"],
            plot_bgcolor=layout_theme["plot_bgcolor"],
            paper_bgcolor=layout_theme["paper_bgcolor"],
            font=layout_theme["font"],
            margin=dict(l=0, r=0, t=10, b=0),
            height=max(260, len(df_gaps) * 36),
        )
        fig_gaps.update_xaxes(showgrid=True, gridcolor=layout_theme["gridcolor"])
        fig_gaps.update_yaxes(showgrid=False)
        st.plotly_chart(fig_gaps, use_container_width=True)

    if well_cov:
        st.markdown("<h4 style='font-size:14px;margin-bottom:8px;'>Well-Covered Required Skills (≥80% Coverage)</h4>", unsafe_allow_html=True)
        wc_badges = "".join(f"<span class='sh-badge sh-badge-success'>✓ {w['skill']} ({w['coverage_percentage']:.0f}%)</span>" for w in well_cov)
        st.markdown(wc_badges, unsafe_allow_html=True)

    st.markdown("<h3 style='font-size:16px;margin-bottom:4px;'>Executive Exports & Individual Development</h3>", unsafe_allow_html=True)
    st.caption("Generate role-level summary documents or inspect candidate development roadmaps.")

    ex1, ex2 = st.columns(2)
    with ex1:
        csv_bytes = _safe_fetch_file(f"{API_BASE_URL}/api/jobs/{jid}/skill-gap-report/export?format=csv", token)
        if csv_bytes:
            st.download_button("Export Report (CSV)", data=csv_bytes, file_name=f"skill_gap_report_job_{jid}.csv",
                                mime="text/csv", use_container_width=True)
    with ex2:
        docx_bytes = _safe_fetch_file(f"{API_BASE_URL}/api/jobs/{jid}/skill-gap-report/export?format=docx", token)
        if docx_bytes:
            st.download_button("Export Report (DOCX)", data=docx_bytes, file_name=f"skill_gap_report_job_{jid}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True)

    with st.expander("🔍 Inspect Individual Candidate Development Plan"):
        cand_map = {f"{_display_name(c.get('name'))} ({_display_email(c.get('email'))})": c.get("candidate_id") for c in candidates if c.get("candidate_id")}
        if cand_map:
            sel_cand_label = st.selectbox("Candidate", list(cand_map.keys()), key="gap_c_sel")
            sel_cid = cand_map[sel_cand_label]
            dev_res = get_cached_candidate_development_report(jid, sel_cid, token)
            _handle_unauthorized(dev_res)
            if isinstance(dev_res, dict) and "error" not in dev_res:
                fit_score = dev_res.get("overall_fit_score", 0.0)
                readiness_lvl = dev_res.get("readiness_level", "not_ready")
                st.markdown(f"**Overall Fit:** {_score_badge(fit_score)} · **Readiness:** `{readiness_lvl.replace('_', ' ').title()}`")

                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                recs = dev_res.get("development_recommendations", [])
                if recs:
                    for i, r in enumerate(recs, 1):
                        st.markdown(f"<div style='font-size:13px;padding:3px 0;'><b>{i}.</b> {r}</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# VIEW: Interview Assistant & Kanban Pipeline
# ---------------------------------------------------------------------------
def show_interview_assistant_view(jobs_list, candidates, token):
    render_recruiter_topbar(
        "Recruitment / Interview Assistant",
        "AI Interview Copilot & ATS Pipeline",
        "Generate targeted technical questions, conduct live simulated interviews with voice synthesis, and track ATS pipeline stages."
    )

    t_sim, t_kanban, t_gen, t_prac = st.tabs([
        "🎙️ Live AI Simulation",
        "📋 Kanban Pipeline Board",
        "🎯 Question Generator",
        "📝 Practice & Assessment",
    ])

    # 1. Live AI Simulation
    with t_sim:
        st.markdown("<h3 style='font-size:16px;margin-bottom:4px;'>Interactive Interview Room</h3>", unsafe_allow_html=True)
        st.caption("AI conducts dynamic, voice-enabled interviews with real-time transcription.")

        sim_c1, sim_c2 = st.columns(2)
        with sim_c1:
            cand_map = {f"{_display_name(c.get('name'))} ({_display_email(c.get('email'))})": c.get("candidate_id") for c in candidates if c.get("candidate_id")}
            sim_cid = cand_map[st.selectbox("Select Candidate", list(cand_map.keys()))] if cand_map else None
        with sim_c2:
            job_map = {f"{j['title']} · {j.get('department') or 'General'}": j["job_id"] for j in jobs_list} if jobs_list else {}
            sim_jid = job_map[st.selectbox("Target Role Position", list(job_map.keys()))] if job_map else None

        active_sid = st.session_state.get("active_interview_session_id")

        b_c1, b_c2 = st.columns([1.5, 1.5])
        with b_c1:
            if st.button("🚀 Start New Interview Session", type="primary", disabled=bool(active_sid)):
                if not sim_cid or not sim_jid:
                    st.error("Select both candidate and position.")
                else:
                    with st.spinner("Initializing AI session..."):
                        c_res = api_request("POST", "/api/interview-sessions", token=token, json={"candidate_id": sim_cid, "job_id": sim_jid})
                        _handle_unauthorized(c_res)
                        if isinstance(c_res, dict) and "session_id" in c_res:
                            new_sid = c_res["session_id"]
                            st.session_state["active_interview_session_id"] = new_sid
                            api_request("POST", f"/api/interview-sessions/{new_sid}/respond", token=token, json={})
                            st.rerun()

        with b_c2:
            if active_sid:
                if st.button("⏹ Conclude Interview Session", type="secondary"):
                    api_request("POST", f"/api/interview-sessions/{active_sid}/complete", token=token)
                    st.session_state.pop("active_interview_session_id", None)
                    st.success("Session concluded.")
                    st.rerun()

        if active_sid:
            s_data = api_request("GET", f"/api/interview-sessions/{active_sid}", token=token)
            _handle_unauthorized(s_data)
            if isinstance(s_data, dict) and "transcript" in s_data:
                transcript = s_data.get("transcript", [])
                st.markdown(f"<div style='font-size:12px;color:var(--text-muted);margin:14px 0;'>Active Session #{active_sid} · {s_data.get('candidate_name')} · {s_data.get('job_title')}</div>", unsafe_allow_html=True)

                voice_on = st.toggle("Voice Audio Playback", value=True, key=f"sim_voice_{active_sid}")

                for i, msg in enumerate(transcript):
                    role = msg.get("role")
                    content = msg.get("content", "")
                    if role == "interviewer":
                        with st.chat_message("assistant"):
                            st.markdown(content)
                            if voice_on and i == len(transcript) - 1:
                                a_bytes = _text_to_speech_bytes(content)
                                if a_bytes:
                                    played_key = f"sim_tts_{active_sid}_{i}"
                                    should_autoplay = not st.session_state.get(played_key, False)
                                    st.audio(a_bytes, format="audio/wav", autoplay=should_autoplay)
                                    st.session_state[played_key] = True
                    else:
                        with st.chat_message("user"):
                            st.markdown(content)

                try:
                    from audio_recorder_streamlit import audio_recorder
                    rec_audio = audio_recorder(key=f"sim_rec_{active_sid}_{len(transcript)}", text="Speak into microphone", neutral_color=_mic_neutral_color())
                    if rec_audio:
                        with st.spinner("Transcribing..."):
                            trans_txt = _speech_to_text(rec_audio)
                        if trans_txt:
                            st.info(f"Transcribed: \"{trans_txt}\"")
                            if st.button("Send Transcribed Response", type="primary"):
                                api_request("POST", f"/api/interview-sessions/{active_sid}/respond", token=token, json={"message": trans_txt})
                                st.rerun()
                except Exception:
                    pass

                chat_txt = st.chat_input("Type candidate response...")
                if chat_txt:
                    api_request("POST", f"/api/interview-sessions/{active_sid}/respond", token=token, json={"message": chat_txt})
                    st.rerun()

    # 2. Kanban Pipeline Board
    with t_kanban:
        st.markdown("<h3 style='font-size:16px;margin-bottom:4px;'>ATS Interview Pipeline Board</h3>", unsafe_allow_html=True)
        st.caption("Visual Kanban board tracking candidate progress through stages.")

        p_res = api_request("GET", "/api/interview-sessions", token=token)
        _handle_unauthorized(p_res)
        sessions = p_res if isinstance(p_res, list) else []

        scheduled = [s for s in sessions if s.get("status") == "scheduled"]
        in_progress = [s for s in sessions if s.get("status") == "in_progress"]
        completed = [s for s in sessions if s.get("status") == "completed"]

        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown(f"""
            <div class='sh-kanban-col'>
                <div class='sh-kanban-header'>
                    <span class='sh-kanban-title'>Scheduled</span>
                    <span class='sh-kanban-badge'>{len(scheduled)}</span>
                </div>
            """, unsafe_allow_html=True)
            for s in scheduled:
                sid = s.get("session_id")
                st.markdown(f"""
                <div class='sh-card-sm' style='margin-bottom:8px;'>
                    <div style='font-weight:600;font-size:13px;'>{s.get('candidate_name')}</div>
                    <div style='font-size:11px;color:var(--text-muted);'>{s.get('job_title')}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Start Interview", key=f"kb_start_{sid}", use_container_width=True, type="secondary"):
                    st.session_state["active_interview_session_id"] = sid
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with k2:
            st.markdown(f"""
            <div class='sh-kanban-col'>
                <div class='sh-kanban-header'>
                    <span class='sh-kanban-title'>In Progress</span>
                    <span class='sh-kanban-badge'>{len(in_progress)}</span>
                </div>
            """, unsafe_allow_html=True)
            for s in in_progress:
                sid = s.get("session_id")
                st.markdown(f"""
                <div class='sh-card-sm' style='margin-bottom:8px;'>
                    <div style='font-weight:600;font-size:13px;'>{s.get('candidate_name')}</div>
                    <div style='font-size:11px;color:var(--text-muted);'>{s.get('job_title')}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Mark Completed", key=f"kb_comp_{sid}", use_container_width=True):
                    api_request("POST", f"/api/interview-sessions/{sid}/complete", token=token)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with k3:
            st.markdown(f"""
            <div class='sh-kanban-col'>
                <div class='sh-kanban-header'>
                    <span class='sh-kanban-title'>Completed</span>
                    <span class='sh-kanban-badge'>{len(completed)}</span>
                </div>
            """, unsafe_allow_html=True)
            for s in completed:
                st.markdown(f"""
                <div class='sh-card-sm' style='margin-bottom:8px;'>
                    <div style='font-weight:600;font-size:13px;'>{s.get('candidate_name')}</div>
                    <div style='font-size:11px;color:var(--text-muted);'>{s.get('job_title')}</div>
                    <span class='sh-badge sh-badge-success'>✓ Finished</span>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # 3. Question Generator
    with t_gen:
        st.markdown("<h3 style='font-size:16px;margin-bottom:4px;'>Role-Grounded Question Generator</h3>", unsafe_allow_html=True)
        st.caption("AI crafts role-specific questions mapped to requirements.")

        if not jobs_list:
            st.info("Please create a job position first.")
        else:
            j_map = {f"{j['title']} · {j.get('department') or 'General'}": j["job_id"] for j in jobs_list}
            sel_j_label = st.selectbox("Job Opening", list(j_map.keys()), key="qgen_job")
            sel_jid = j_map[sel_j_label]

            c1, c2 = st.columns(2)
            with c1:
                q_type = st.selectbox("Question Focus", ["Technical", "Behavioral", "Scenario-based"], key="qgen_type")
            with c2:
                q_count = st.number_input("Question Count", min_value=1, max_value=10, value=3, key="qgen_count")

            if st.button("Generate Interview Questions", type="primary", key="btn_gen_iq"):
                with st.spinner("Generating role-specific questions..."):
                    res = api_request("GET", f"/api/jobs/{sel_jid}/interview-questions?question_type={q_type}&count={q_count}", token=token)
                _handle_unauthorized(res)
                if isinstance(res, dict) and "questions" in res:
                    st.session_state[f"iq_res_{sel_jid}"] = res
                else:
                    st.error("Failed to generate questions. Ensure an AI key is set in .env.")

            saved_q = st.session_state.get(f"iq_res_{sel_jid}")
            if saved_q and "questions" in saved_q:
                st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
                for q in saved_q["questions"]:
                    st.markdown(f"""
                    <div class='sh-card-sm' style='margin-bottom:8px;'>
                        <div style='font-size:14px;font-weight:600;'>{q.get('question_number', 1)}. {q.get('question_text')}</div>
                        <div style='font-size:11px;color:var(--text-subtle);margin-top:4px;'>{q.get('question_type')} · {q.get('sub_type', 'General')} · {q.get('estimated_duration', '3-5 min')}</div>
                    </div>
                    """, unsafe_allow_html=True)

    # 4. Practice & Assessment
    with t_prac:
        st.markdown("<h3 style='font-size:16px;margin-bottom:4px;'>Practice & Assessment Generator</h3>", unsafe_allow_html=True)
        st.caption("Generate difficulty-tiered questions or MCQ assessments.")

        if jobs_list:
            j_map = {f"{j['title']} · {j.get('department') or 'General'}": j["job_id"] for j in jobs_list}
            sel_j_label = st.selectbox("Target Role", list(j_map.keys()), key="pq_job")
            sel_jid = j_map[sel_j_label]

            p1, p2, p3 = st.columns(3)
            with p1:
                pq_type = st.selectbox("Focus Area", ["Technical", "Behavioral", "Scenario-based"], key="pq_t_sel")
            with p2:
                pq_diff = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1, key="pq_d_sel")
            with p3:
                pq_fmt = st.selectbox("Format", ["Multiple Choice", "Open-ended"], key="pq_f_sel")

            if st.button("Generate Practice Questions", type="primary", key="btn_gen_pq"):
                with st.spinner("Generating assessment questions..."):
                    res = api_request("GET", f"/api/jobs/{sel_jid}/interview-questions/practice?question_type={pq_type}&difficulty={pq_diff}&question_format={pq_fmt}&count=3", token=token)
                _handle_unauthorized(res)
                if isinstance(res, dict) and "questions" in res:
                    st.session_state[f"pq_res_{sel_jid}"] = res
                else:
                    st.error("Could not generate questions.")

            saved_pq = st.session_state.get(f"pq_res_{sel_jid}")
            if saved_pq and "questions" in saved_pq:
                for q in saved_pq["questions"]:
                    st.markdown(f"""
                    <div class='sh-card-sm' style='margin-top:10px;'>
                        <div style='font-size:14px;font-weight:600;'>{q.get('question_number', 1)}. {q.get('question_text')}</div>
                        <div style='font-size:11px;color:var(--text-subtle);margin-top:4px;'>{pq_diff} · {pq_fmt}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if pq_fmt == "Multiple Choice" and q.get("options"):
                        for opt in q["options"]:
                            st.markdown(f"<div style='font-size:13px;padding:3px 12px;'>• <b>{opt.get('label')}.</b> {opt.get('text')}</div>", unsafe_allow_html=True)
                        with st.expander(f"Answer Key — Q{q.get('question_number')}"):
                            st.markdown(f"**Correct:** {q.get('correct_option')}  \n{q.get('explanation', '')}")

# ---------------------------------------------------------------------------
# VIEW: Resume Parser
# ---------------------------------------------------------------------------
def show_resume_parser_view(token):
    render_recruiter_topbar(
        "Workspace / Parser",
        "Resume Parser & Ingestion Engine",
        "Upload PDF, DOCX, or TXT documents for automatic extraction of skills, experience, and contact credentials."
    )

    st.markdown("<h3 style='font-size:16px;margin-bottom:4px;'>Resume Upload Dropzone</h3>", unsafe_allow_html=True)
    st.caption("PyMuPDF and NLP parser extract all skills, experiences, and education automatically.")

    uploaded_files = st.file_uploader(
        "Drop files here or click to browse",
        accept_multiple_files=True,
        type=["pdf", "docx", "txt"],
        label_visibility="collapsed",
    )

    if uploaded_files:
        st.markdown(f"<div style='font-size:12px;color:var(--text-muted);margin:10px 0;'>Selected <b>{len(uploaded_files)}</b> files:</div>", unsafe_allow_html=True)
        for uf in uploaded_files:
            st.markdown(f"<div class='sh-card-sm' style='padding:8px 12px;margin-bottom:4px;'>📄 <b>{uf.name}</b> ({_fmt_bytes(uf.size)})</div>", unsafe_allow_html=True)

    if st.button("Process Uploaded Resumes", type="primary", disabled=not uploaded_files, use_container_width=True):
        pb = st.progress(0)
        results = []
        for i, uf in enumerate(uploaded_files):
            res = api_request("POST", "/api/candidates/upload", token=token, files={"file": (uf.name, uf.getvalue(), uf.type)})
            _handle_unauthorized(res)
            status = "Parsed" if "error" not in res else "Error"
            results.append({"File": uf.name, "Status": status, "Candidate": res.get("name", "—")})
            pb.progress((i + 1) / len(uploaded_files))
        invalidate_candidate_caches()
        st.success(f"Processed {len(results)} resumes!")
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    with st.expander("⚡ Need sample candidate data? Parse demo resumes from directory"):
        st.caption("Ingests pre-loaded sample resumes from the local resumes/ folder for instant testing.")
        if st.button("Parse Demo Resumes (Quick Seed)", key="btn_parse_demo_resumes", type="secondary"):
            demo_dir = "resumes"
            if os.path.exists(demo_dir):
                files = [f for f in os.listdir(demo_dir) if f.endswith((".pdf", ".docx", ".txt"))]
                if files:
                    pb = st.progress(0)
                    for i, fn in enumerate(files):
                        with open(os.path.join(demo_dir, fn), "rb") as f:
                            api_request("POST", "/api/candidates/upload", token=token, files={"file": (fn, f, "application/octet-stream")})
                        pb.progress((i + 1) / len(files))
                    invalidate_candidate_caches()
                    st.success(f"Successfully seeded {len(files)} demo candidates!")
                    st.rerun()
                else:
                    st.warning("No files found in resumes/")

# ---------------------------------------------------------------------------
# VIEW: Settings
# ---------------------------------------------------------------------------
def show_settings_view(user, candidates, jobs_list, token):
    render_recruiter_topbar(
        "Workspace / Settings",
        "Workspace Preferences & Diagnostics",
        "Manage account settings, toggle interface themes, and verify system integration health."
    )

    s1, s2 = st.columns(2)
    with s1:
        st.markdown("<h3 style='font-size:16px;margin-bottom:4px;'>Account Profile</h3>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style='margin-top:10px;'>
            <div style='font-size:12px;color:var(--text-subtle);'>Full Name</div>
            <div style='font-size:14px;font-weight:600;'>{user.get('full_name')}</div>
            <div style='font-size:12px;color:var(--text-subtle);margin-top:8px;'>Email</div>
            <div style='font-size:14px;font-weight:600;'>{user.get('email')}</div>
            <div style='font-size:12px;color:var(--text-subtle);margin-top:8px;'>Role / Company</div>
            <div style='font-size:14px;font-weight:600;'>{user.get('job_title')} · {user.get('company_name')}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<h3 style='font-size:16px;margin-bottom:4px;'>Display Theme</h3>", unsafe_allow_html=True)
        cur_theme = st.session_state.get("theme", "dark")
        theme_pick = st.radio("Theme Mode", ["Dark", "Light"], index=0 if cur_theme == "dark" else 1, horizontal=True)
        if theme_pick.lower() != cur_theme:
            st.session_state["theme"] = theme_pick.lower()
            st.rerun()

    with s2:
        st.markdown("<h3 style='font-size:16px;margin-bottom:4px;'>Database & Cache Management</h3>", unsafe_allow_html=True)
        st.markdown(f"**Candidates in DB:** {len(candidates)}  \n**Active Jobs:** {len(jobs_list)}")

        if st.button("Flush Cache Memory", use_container_width=True, type="secondary"):
            invalidate_candidate_caches()
            invalidate_job_caches()
            st.success("Memory cache cleared.")

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        if st.button("Clear All Candidates from DB", use_container_width=True):
            res = api_request("DELETE", "/api/candidates", token=token)
            _handle_unauthorized(res)
            invalidate_candidate_caches()
            st.success("Cleared all candidate records.")
            st.rerun()

# ---------------------------------------------------------------------------
# VIEW: Recruiter Shell Orchestrator
# ---------------------------------------------------------------------------
def show_dashboard():
    load_css()
    token = st.session_state.get("auth_token")
    user = st.session_state.get("user", {})

    user_role = str(user.get("job_title", "")).strip().lower()
    if user_role == "candidate":
        show_candidate_dashboard(token, user)
        return

    candidates_res, candidates, all_skills_flat = get_cached_candidates(token, CANDIDATE_FETCH_LIMIT)
    _handle_unauthorized(candidates_res)
    summary_res = get_cached_analytics_summary(token)
    _handle_unauthorized(summary_res)
    jobs_list = get_cached_jobs(token)

    total_candidates = len(candidates)
    if isinstance(summary_res, dict) and "total_candidates" in summary_res:
        total_candidates = summary_res["total_candidates"]

    with st.sidebar:
        st.markdown(f"""
        <div class='sh-brand-box'>
            <div class='sh-avatar' style='width:32px;height:32px;font-size:14px;background:var(--primary);'>{render_svg('sparkles', 18, '#ffffff')}</div>
            <div>
                <div class='sh-brand-title'>SmartHire AI</div>
                <span class='sh-brand-badge'>ENTERPRISE ATS</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        current_nav = st.session_state.get("active_nav", "Dashboard")

        # Group 1: OVERVIEW
        st.markdown("<div class='sh-nav-group-label'>Overview</div>", unsafe_allow_html=True)
        if st.button(f"{'▸ ' if current_nav == 'Dashboard' else '  '}Dashboard", key="nav_dash", use_container_width=True,
                     type="primary" if current_nav == "Dashboard" else "secondary"):
            st.session_state["active_nav"] = "Dashboard"
            st.rerun()

        # Group 2: RECRUITMENT
        st.markdown("<div class='sh-nav-group-label'>Recruitment</div>", unsafe_allow_html=True)
        cand_lbl = f"{'▸ ' if current_nav == 'Candidates' else '  '}Candidates ({total_candidates})"
        if st.button(cand_lbl, key="nav_cand", use_container_width=True,
                     type="primary" if current_nav == "Candidates" else "secondary"):
            st.session_state["active_nav"] = "Candidates"
            st.rerun()

        jobs_lbl = f"{'▸ ' if current_nav == 'Jobs' else '  '}Jobs ({len(jobs_list)})"
        if st.button(jobs_lbl, key="nav_jobs", use_container_width=True,
                     type="primary" if current_nav == "Jobs" else "secondary"):
            st.session_state["active_nav"] = "Jobs"
            st.rerun()

        if st.button(f"{'▸ ' if current_nav == 'Job Matcher' else '  '}Job Matcher", key="nav_match", use_container_width=True,
                     type="primary" if current_nav == "Job Matcher" else "secondary"):
            st.session_state["active_nav"] = "Job Matcher"
            st.rerun()

        if st.button(f"{'▸ ' if current_nav == 'Interview Assistant' else '  '}Interviews", key="nav_interviews", use_container_width=True,
                     type="primary" if current_nav == "Interview Assistant" else "secondary"):
            st.session_state["active_nav"] = "Interview Assistant"
            st.rerun()

        # Group 3: INSIGHTS
        st.markdown("<div class='sh-nav-group-label'>Insights</div>", unsafe_allow_html=True)
        if st.button(f"{'▸ ' if current_nav == 'Analytics' else '  '}Analytics", key="nav_analytics", use_container_width=True,
                     type="primary" if current_nav == "Analytics" else "secondary"):
            st.session_state["active_nav"] = "Analytics"
            st.rerun()

        if st.button(f"{'▸ ' if current_nav == 'Skill Gap Report' else '  '}Skill Gap Report", key="nav_gap", use_container_width=True,
                     type="primary" if current_nav == "Skill Gap Report" else "secondary"):
            st.session_state["active_nav"] = "Skill Gap Report"
            st.rerun()

        # Group 4: WORKSPACE
        st.markdown("<div class='sh-nav-group-label'>Workspace</div>", unsafe_allow_html=True)
        if st.button(f"{'▸ ' if current_nav == 'Resume Parser' else '  '}Resume Parser", key="nav_parser", use_container_width=True,
                     type="primary" if current_nav == "Resume Parser" else "secondary"):
            st.session_state["active_nav"] = "Resume Parser"
            st.rerun()

        if st.button(f"{'▸ ' if current_nav == 'Settings' else '  '}Settings", key="nav_settings", use_container_width=True,
                     type="primary" if current_nav == "Settings" else "secondary"):
            st.session_state["active_nav"] = "Settings"
            st.rerun()

        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)

        theme_cur = st.session_state.get("theme", "dark")
        theme_toggle_text = "☀️ Light Mode" if theme_cur == "dark" else "🌙 Dark Mode"
        if st.button(theme_toggle_text, key="theme_toggle_btn", use_container_width=True, type="secondary"):
            st.session_state["theme"] = "light" if theme_cur == "dark" else "dark"
            st.rerun()

        st.markdown(f"""
        <div style='padding:12px;border-top:1px solid var(--border);margin-top:10px;'>
            <div style='font-size:13px;font-weight:600;color:var(--text-primary);'>{user.get('full_name', 'Recruiter')}</div>
            <div style='font-size:11px;color:var(--text-subtle);'>{user.get('job_title', 'HR')} · {user.get('company_name', 'Acme')}</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Sign Out", key="sidebar_sign_out", use_container_width=True, type="secondary"):
            for key in ("auth_token", "user", "active_nav", "selected_candidate_id"):
                st.session_state.pop(key, None)
            st.rerun()

    if current_nav == "Dashboard":
        show_dashboard_overview(candidates, jobs_list, summary_res, all_skills_flat, token)
    elif current_nav == "Candidates":
        show_candidates_view(candidates, total_candidates, all_skills_flat, jobs_list, candidates_res, token)
    elif current_nav == "Jobs":
        show_jobs_view(jobs_list, candidates, token)
    elif current_nav == "Job Matcher":
        show_job_matcher_view(jobs_list, candidates, token)
    elif current_nav == "Analytics":
        show_analytics_view(candidates, total_candidates, token)
    elif current_nav == "Skill Gap Report":
        show_skill_gap_view(jobs_list, candidates, token)
    elif current_nav == "Interview Assistant":
        show_interview_assistant_view(jobs_list, candidates, token)
    elif current_nav == "Resume Parser":
        show_resume_parser_view(token)
    elif current_nav == "Settings":
        show_settings_view(user, candidates, jobs_list, token)

# ---------------------------------------------------------------------------
# VIEW: Candidate Portal
# ---------------------------------------------------------------------------
def show_candidate_dashboard(token: str, user: dict):
    load_css()
    try:
        from audio_recorder_streamlit import audio_recorder
    except Exception:
        audio_recorder = None

    with st.sidebar:
        st.markdown(f"""
        <div class='sh-brand-box'>
            <div class='sh-avatar' style='width:32px;height:32px;background:var(--primary);'>{render_svg('sparkles', 18, '#ffffff')}</div>
            <div>
                <div class='sh-brand-title'>SmartHire AI</div>
                <span class='sh-brand-badge'>CANDIDATE PORTAL</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        user_name = user.get("full_name", "Candidate")
        user_email = user.get("email", "")

        st.markdown(f"""
        <div class='sh-card-sm' style='margin-bottom:12px;'>
            <div style='font-size:13px;font-weight:600;'>{user_name}</div>
            <div style='font-size:11px;color:var(--text-subtle);'>{user_email}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div class='sh-nav-group-label'>Navigation</div>", unsafe_allow_html=True)
        nav_choice = st.radio(
            "Navigation",
            [
                "Overview & Profile",
                "Resume Intelligence & ATS",
                "Demo Practice Questions",
                "AI Mock Interview",
                "Interview Reports & History",
            ],
            label_visibility="collapsed",
            key="candidate_nav_radio",
        )

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
        theme_cur = st.session_state.get("theme", "dark")
        theme_toggle_text = "☀️ Light Mode" if theme_cur == "dark" else "🌙 Dark Mode"
        if st.button(theme_toggle_text, key="cand_theme_toggle_btn", use_container_width=True, type="secondary"):
            st.session_state["theme"] = "light" if theme_cur == "dark" else "dark"
            st.rerun()

        if st.button("Sign Out", use_container_width=True, key="candidate_logout_btn", type="secondary"):
            st.session_state.clear()
            st.rerun()

    prof_res = api_request("GET", "/api/candidate/profile", token=token)
    _handle_unauthorized(prof_res)
    candidate_profile = prof_res if isinstance(prof_res, dict) and "error" not in prof_res else {}

    skills_list = candidate_profile.get("skills", [])
    exp_list = candidate_profile.get("experience", [])
    proj_list = candidate_profile.get("projects", [])
    edu_list = candidate_profile.get("education", [])
    has_resume = bool(candidate_profile.get("resume_path"))

    if nav_choice == "Overview & Profile":
        render_recruiter_topbar("Candidate / Hub", "Candidate Profile & Career Hub", "Manage your technical portfolio, credentials, and career materials.")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
            <div class='sh-stat-card'>
                <div class='sh-stat-label'>Resume Status</div>
                <div class='sh-stat-value' style='color:{'#10B981' if has_resume else '#F59E0B'};font-size:20px;'>{'Uploaded' if has_resume else 'Pending'}</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class='sh-stat-card'>
                <div class='sh-stat-label'>Identified Skills</div>
                <div class='sh-stat-value' style='font-size:20px;'>{len(skills_list)}</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class='sh-stat-card'>
                <div class='sh-stat-label'>Experience Roles</div>
                <div class='sh-stat-value' style='font-size:20px;'>{len(exp_list)}</div>
            </div>
            """, unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
            <div class='sh-stat-card'>
                <div class='sh-stat-label'>Projects</div>
                <div class='sh-stat-value' style='font-size:20px;'>{len(proj_list)}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        col_l, col_r = st.columns([1.3, 1])
        with col_l:
            st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Edit Profile Details</h3>", unsafe_allow_html=True)

            p_name = st.text_input("Full Name", value=candidate_profile.get("name") or user_name, key="cp_name")
            p_email = st.text_input("Email", value=candidate_profile.get("email") or user_email, key="cp_email")
            p_phone = st.text_input("Phone", value=candidate_profile.get("phone") or "", placeholder="+1 555 000 0000", key="cp_phone")
            p_skills = st.text_input("Technical Skills (Comma-separated)", value=", ".join(skills_list), placeholder="e.g. Python, SQL, Docker, React", key="cp_skills")

            if st.button("Save Profile Changes", type="primary", use_container_width=True):
                update_payload = {
                    "name": p_name.strip(),
                    "email": p_email.strip(),
                    "phone": p_phone.strip() or None,
                    "skills": [s.strip() for s in p_skills.split(",") if s.strip()],
                    "experience": exp_list,
                    "education": edu_list,
                    "projects": proj_list,
                }
                save_res = api_request("PUT", "/api/candidate/profile", token=token, json=update_payload)
                _handle_unauthorized(save_res)
                if "error" in save_res:
                    st.error(save_res["error"])
                else:
                    st.success("Profile updated!")
                    st.rerun()

        with col_r:
            st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Parsed Work History & Credentials</h3>", unsafe_allow_html=True)
            st.caption("Extracted automatically from your uploaded resume.")

            if exp_list:
                st.markdown("<div style='font-size:12px;font-weight:600;color:var(--text-subtle);margin-top:8px;'>WORK EXPERIENCE</div>", unsafe_allow_html=True)
                for exp in exp_list[:4]:
                    txt = exp.get("raw") if isinstance(exp, dict) else str(exp)
                    st.markdown(f"<div style='font-size:13px;padding:3px 0;'>• {txt}</div>", unsafe_allow_html=True)

            if edu_list:
                st.markdown("<div style='font-size:12px;font-weight:600;color:var(--text-subtle);margin-top:12px;'>EDUCATION</div>", unsafe_allow_html=True)
                for edu in edu_list[:3]:
                    txt = edu.get("raw") if isinstance(edu, dict) else str(edu)
                    st.markdown(f"<div style='font-size:13px;padding:3px 0;'>🎓 {txt}</div>", unsafe_allow_html=True)

            if proj_list:
                st.markdown("<div style='font-size:12px;font-weight:600;color:var(--text-subtle);margin-top:12px;'>PROJECTS</div>", unsafe_allow_html=True)
                for proj in proj_list[:3]:
                    txt = proj.get("raw") if isinstance(proj, dict) else str(proj)
                    st.markdown(f"<div style='font-size:13px;padding:3px 0;'>💼 {txt}</div>", unsafe_allow_html=True)

    elif nav_choice == "Resume Intelligence & ATS":
        render_recruiter_topbar("Candidate / ATS", "AI Resume Intelligence & ATS Screening", "Upload your resume for deep AI parsing, ATS optimization scoring, and role alignment.")

        st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Upload Resume Document</h3>", unsafe_allow_html=True)
        up_file = st.file_uploader("Select Resume File", type=["pdf", "docx", "txt"], key="cand_up_res")
        if up_file:
            if st.button("Parse Resume & Update Profile", type="primary"):
                files = {"file": (up_file.name, up_file.getvalue(), up_file.type or "application/octet-stream")}
                up_res = api_request("POST", "/api/candidate/resume/upload", token=token, files=files)
                _handle_unauthorized(up_res)
                if "error" in up_res:
                    st.error(up_res["error"])
                else:
                    st.success("Resume parsed successfully!")
                    st.rerun()

        jobs_res = api_request("GET", "/api/jobs", token=token, params={"limit": 50})
        _handle_unauthorized(jobs_res)
        jobs_list = jobs_res if isinstance(jobs_res, list) else []

        st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Target Role Alignment</h3>", unsafe_allow_html=True)
        j_opts = {"General Software Role": None}
        for j in jobs_list:
            j_opts[f"{j.get('title')} ({j.get('department') or 'General'})"] = j.get("job_id")
        sel_label = st.selectbox("Benchmark Against Role", list(j_opts.keys()))
        sel_jid = j_opts[sel_label]

        if st.button("Run Comprehensive AI Resume Audit", type="primary"):
            with st.spinner("Analyzing resume against role requirements..."):
                an_res = api_request("POST", "/api/candidate/resume/analyze", token=token, json={"target_job_id": sel_jid})
            _handle_unauthorized(an_res)
            if "error" in an_res:
                st.error(an_res["error"])
            else:
                st.session_state["latest_resume_analysis"] = an_res
                st.success("Audit complete!")

        analysis_data = st.session_state.get("latest_resume_analysis")
        if analysis_data and "analysis" in analysis_data:
            an = analysis_data["analysis"]
            ats = an.get("ats_feedback", {})
            ats_score = ats.get("ats_score", 75)

            st.markdown(f"""
            <div class='sh-stat-card' style='text-align:center;margin-bottom:16px;'>
                <div class='sh-stat-label'>ATS Compatibility Score</div>
                <div class='sh-stat-value' style='color:{_score_bar_color(ats_score)};margin:8px 0;'>{ats_score}/100</div>
                <div style='font-size:13px;color:var(--text-muted);'>{ats.get('formatting_assessment', 'Standard structure')}</div>
            </div>
            """, unsafe_allow_html=True)

            c_s, c_w = st.columns(2)
            with c_s:
                st.markdown("<h4 style='color:#10B981;'>Core Strengths</h4>", unsafe_allow_html=True)
                for s in an.get("strengths", []):
                    st.markdown(f"<div style='font-size:13px;padding:2px 0;'>• {s}</div>", unsafe_allow_html=True)
            with c_w:
                st.markdown("<h4 style='color:#F59E0B;'>Areas for Growth</h4>", unsafe_allow_html=True)
                for imp in an.get("improvement_areas", []):
                    st.markdown(f"<div style='font-size:13px;padding:2px 0;'>• {imp}</div>", unsafe_allow_html=True)

    elif nav_choice == "Demo Practice Questions":
        render_recruiter_topbar("Candidate / Practice", "Interactive Practice & Self-Assessment", "Practice role-specific interview questions with immediate AI scoring.")

        st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Configure Practice Session</h3>", unsafe_allow_html=True)
        pq_type = st.selectbox("Focus Area", ["Technical", "Behavioral", "Scenario-based"], key="cand_pq_type")
        pq_diff = st.selectbox("Difficulty Tier", ["Easy", "Medium", "Hard"], index=1, key="cand_pq_diff")
        pq_fmt = st.selectbox("Format", ["Open-ended", "Multiple Choice"], key="cand_pq_fmt")

        if st.button("Generate Tailored Practice Questions", type="primary", use_container_width=True):
            res = api_request("GET", f"/api/candidate/practice-questions?question_type={pq_type}&difficulty={pq_diff}&question_format={pq_fmt}&count=3", token=token)
            _handle_unauthorized(res)
            if "error" in res:
                st.error(res["error"])
            else:
                st.session_state["cand_pq_qs"] = res.get("questions", [])
                st.session_state["practice_feedback_cache"] = {}
                st.success("Questions generated!")

        qs = st.session_state.get("cand_pq_qs", [])
        for q in qs:
            q_num = q.get("question_number", 1)
            q_text = q.get("question_text", "")
            is_mcq = (q.get("question_format") == "Multiple Choice") or bool(q.get("options"))

            st.markdown(f"""
            <div style='display:flex;justify-content:space-between;align-items:center;'>
                <span style='font-size:12px;font-weight:700;color:var(--primary);text-transform:uppercase;'>Question {q_num}</span>
                <span style='font-size:11px;color:var(--text-subtle);'>{q.get('sub_type', 'General')} · {q.get('estimated_duration', '3 min')}</span>
            </div>
            <div style='font-size:15px;font-weight:600;margin:8px 0 14px;'>{q_text}</div>
            """, unsafe_allow_html=True)

            if is_mcq:
                opts = q.get("options", [])
                opt_labels = [f"{o.get('label')}: {o.get('text')}" for o in opts]
                selected_opt = st.radio(f"Select option for Q{q_num}:", opt_labels, key=f"mcq_choice_{q_num}")
                if st.button(f"Check Answer for Q{q_num}", key=f"btn_check_mcq_{q_num}", type="secondary"):
                    chosen = selected_opt.split(":")[0].strip() if selected_opt else ""
                    correct = q.get("correct_option", "")
                    if chosen == correct:
                        st.success(f"✓ Correct! Option {chosen} is the right choice.")
                    else:
                        st.error(f"✗ Option {chosen} is incorrect. The correct answer is {correct}.")
                    if q.get("explanation"):
                        st.info(f"💡 Explanation: {q.get('explanation')}")
            else:
                ans_text = st.text_area("Your Response", placeholder="Type your answer here or speak via microphone...", key=f"cand_open_ans_{q_num}", height=90)
                if audio_recorder:
                    rec_audio = audio_recorder(key=f"cand_rec_pq_{q_num}", text="", recording_color="#e11d48", neutral_color=_mic_neutral_color())
                    if rec_audio:
                        with st.spinner("Transcribing voice..."):
                            trans = _speech_to_text(rec_audio)
                        if trans:
                            st.info(f"Transcribed: \"{trans}\"")
                            ans_text = trans

                if st.button(f"Submit Answer for AI Evaluation (Q{q_num})", type="primary", key=f"btn_sub_open_{q_num}"):
                    if not ans_text.strip():
                        st.warning("Please type or speak an answer before submitting.")
                    else:
                        with st.spinner("AI evaluating answer..."):
                            eval_payload = {
                                "question_text": q_text,
                                "question_type": pq_type,
                                "difficulty": pq_diff,
                                "candidate_answer": ans_text.strip(),
                            }
                            eval_res = api_request("POST", "/api/candidate/practice-answers", token=token, json=eval_payload)
                        _handle_unauthorized(eval_res)
                        if "error" in eval_res:
                            st.error(eval_res["error"])
                        else:
                            if "practice_feedback_cache" not in st.session_state:
                                st.session_state["practice_feedback_cache"] = {}
                            st.session_state["practice_feedback_cache"][q_num] = eval_res
                            st.success("Evaluation ready!")

                fb_res = st.session_state.get("practice_feedback_cache", {}).get(q_num)
                if fb_res and "feedback" in fb_res:
                    fb = fb_res["feedback"]
                    score_v = fb.get("score", 7)
                    st.markdown(f"""
                    <div class='sh-card-sm' style='margin-top:12px;border-left:3px solid var(--primary);'>
                        <div style='font-size:14px;font-weight:700;color:{_score_bar_color(score_v * 10)};'>Score: {score_v}/10 · {fb.get('verdict', '')}</div>
                        <div style='font-size:13px;color:var(--text-muted);margin-top:4px;'>{fb.get('evaluation_summary', '')}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if fb.get("model_answer"):
                        st.markdown(f"<div style='font-size:12px;padding:8px 0;'><b>Exemplar Answer:</b> {fb.get('model_answer')}</div>", unsafe_allow_html=True)

    elif nav_choice == "AI Mock Interview":
        render_recruiter_topbar("Candidate / Mock Room", "Live AI Mock Interview Room", "Interactive conversational interview with real-time speech recognition.")

        active_mock_id = st.session_state.get("cand_active_mock_id")
        if not active_mock_id:
            st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Launch Adaptive Mock Interview</h3>", unsafe_allow_html=True)
            st.caption("AI interviewer adapts to your answers in real time.")

            jobs_res = api_request("GET", "/api/jobs", token=token, params={"limit": 50})
            _handle_unauthorized(jobs_res)
            jobs_list = jobs_res if isinstance(jobs_res, list) else []

            j_opts = {j.get("title"): j.get("job_id") for j in jobs_list} if jobs_list else {}
            if j_opts:
                sel_m_job = st.selectbox("Target Role", list(j_opts.keys()))
                sel_m_jid = j_opts[sel_m_job]
            else:
                sel_m_jid = None

            c1, c2 = st.columns(2)
            with c1:
                m_type = st.selectbox("Interview Focus", ["Technical", "Behavioral", "mixed"])
            with c2:
                m_diff = st.selectbox("Difficulty Tier", ["Medium", "Easy", "Hard"])

            if st.button("Start Adaptive Mock Interview", type="primary", use_container_width=True):
                with st.spinner("Initializing interview session..."):
                    payload = {"job_id": sel_m_jid, "interview_type": m_type, "difficulty": m_diff}
                    s_res = api_request("POST", "/api/candidate/mock-interview/start", token=token, json=payload)
                _handle_unauthorized(s_res)
                if "error" in s_res:
                    st.error(s_res["error"])
                else:
                    new_id = s_res["session_id"]
                    st.session_state["cand_active_mock_id"] = new_id
                    init_res = api_request("POST", f"/api/candidate/mock-interview/{new_id}/respond", token=token, json={})
                    _handle_unauthorized(init_res)
                    st.rerun()
        else:
            s_res = api_request("GET", f"/api/candidate/mock-interviews/{active_mock_id}", token=token)
            _handle_unauthorized(s_res)
            session = s_res if isinstance(s_res, dict) and "error" not in s_res else None

            if not session:
                st.error("Session not found.")
                if st.button("Reset Session"):
                    st.session_state.pop("cand_active_mock_id", None)
                    st.rerun()
            elif session.get("status") == "completed":
                st.markdown("<h3 style='font-size:18px;color:#10B981;'>🎉 Mock Interview Completed!</h3>", unsafe_allow_html=True)
                fb = session.get("feedback") or {}
                ov_score = fb.get("overall_score", 80)
                verdict = fb.get("verdict", "Strong Candidate")

                st.markdown(f"""
                <div class='sh-stat-card' style='text-align:center;margin:14px 0;'>
                    <div class='sh-stat-label'>Overall Evaluation Score</div>
                    <div class='sh-stat-value' style='color:{_score_bar_color(ov_score)};margin:6px 0;'>{ov_score}/100</div>
                    <div style='font-weight:600;'>{verdict}</div>
                </div>
                """, unsafe_allow_html=True)

                comps = fb.get("competency_scores", {})
                if comps:
                    st.markdown("<h4 style='font-size:14px;margin-bottom:8px;'>Competency Breakdown</h4>", unsafe_allow_html=True)
                    for k, v in comps.items():
                        st.markdown(f"<div style='display:flex;justify-content:space-between;font-size:12px;'><span>{k.replace('_', ' ').title()}</span><b>{v}%</b></div>", unsafe_allow_html=True)
                        st.progress(v / 100)

                st.markdown(f"<div style='font-size:13px;color:var(--text-muted);margin-top:14px;'>{fb.get('detailed_feedback') or fb.get('key_takeaways', '')}</div>", unsafe_allow_html=True)

                if st.button("Start Another Mock Interview", type="primary"):
                    st.session_state.pop("cand_active_mock_id", None)
                    st.rerun()
            else:
                transcript = session.get("transcript", [])
                st.markdown(f"<div style='font-size:13px;color:var(--text-muted);margin-bottom:12px;'>Role: <b>{session.get('job_title', 'Interview')}</b> · Exchanges: {len(transcript)}</div>", unsafe_allow_html=True)

                voice_on = st.toggle("Voice Audio Playback", value=True, key=f"cand_mock_voice_{active_mock_id}")

                for i, msg in enumerate(transcript):
                    role = msg.get("role")
                    content = msg.get("content", "")
                    with st.chat_message("assistant" if role == "interviewer" else "user"):
                        st.markdown(content)
                        if voice_on and role == "interviewer" and i == len(transcript) - 1:
                            a_bytes = _text_to_speech_bytes(content)
                            if a_bytes:
                                played_k = f"mock_tts_{active_mock_id}_{i}"
                                should_auto = not st.session_state.get(played_k, False)
                                st.audio(a_bytes, format="audio/wav", autoplay=should_auto)
                                st.session_state[played_k] = True

                sub_msg = None
                if audio_recorder:
                    st.caption("🎙️ Record spoken answer:")
                    rec_voice = audio_recorder(key=f"mock_mic_{active_mock_id}_{len(transcript)}", text="", recording_color="#e11d48", neutral_color=_mic_neutral_color())
                    if rec_voice:
                        with st.spinner("Transcribing..."):
                            trans_t = _speech_to_text(rec_voice)
                        if trans_t:
                            st.info(f"Transcribed: \"{trans_t}\"")
                            if st.button("Send Transcribed Voice Answer", type="primary"):
                                sub_msg = trans_t

                chat_inp = st.chat_input("Speak or type response...")
                if chat_inp:
                    sub_msg = chat_inp

                if sub_msg:
                    with st.spinner("Interviewer is evaluating..."):
                        resp_m = api_request("POST", f"/api/candidate/mock-interview/{active_mock_id}/respond", token=token, json={"message": sub_msg})
                    _handle_unauthorized(resp_m)
                    st.rerun()

                if st.button("Conclude & Generate Evaluation Report", type="secondary"):
                    with st.spinner("Generating performance scorecard..."):
                        comp_m = api_request("POST", f"/api/candidate/mock-interview/{active_mock_id}/complete", token=token)
                    _handle_unauthorized(comp_m)
                    st.rerun()

    elif nav_choice == "Interview Reports & History":
        render_recruiter_topbar("Candidate / History", "Interview Reports & History", "Review past performance evaluations and competency scorecards.")
        hist_res = api_request("GET", "/api/candidate/mock-interviews", token=token)
        _handle_unauthorized(hist_res)
        sessions = hist_res if isinstance(hist_res, list) else []
        if not sessions:
            st.info("No completed mock interviews yet.")
        else:
            for s in sessions:
                sid = s.get("session_id")
                fb = s.get("feedback") or {}
                ov_score = fb.get("overall_score")
                st.markdown(f"""
                <div class='sh-card-sm' style='margin-bottom:8px;'>
                    <div style='display:flex;justify-content:space-between;align-items:center;'>
                        <span style='font-weight:600;font-size:14px;'>{s.get('job_title', 'Interview')} · {s.get('created_at', '')[:10]}</span>
                        <span>{_score_badge(ov_score) if ov_score else f"<span class='sh-badge sh-badge-neutral'>{s.get('status')}</span>"}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# VIEW: Authentication (Login & Register)
# ---------------------------------------------------------------------------
def show_login():
    load_css()
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown(f"""
        <div style='text-align:center;margin-bottom:24px;margin-top:40px;'>
            <div class='sh-avatar' style='width:44px;height:44px;margin:0 auto 12px;background:var(--primary);'>{render_svg('sparkles', 22, '#ffffff')}</div>
            <h1 style='font-size:24px;font-weight:700;letter-spacing:-0.03em;'>SmartHire AI</h1>
            <div style='font-size:13px;color:var(--text-muted);'>Enterprise Recruitment Platform</div>
        </div>
        """, unsafe_allow_html=True)

        expired_msg = st.session_state.get("session_expired_message")
        if expired_msg:
            st.warning(f"⚠️ {expired_msg}")

        st.markdown("<h3 style='font-size:16px;margin-bottom:14px;'>Sign in to your account</h3>", unsafe_allow_html=True)

        email = st.text_input("Email or Account Name", placeholder="you@company.com or username", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        c1, c2 = st.columns(2)
        with c1:
            login_clicked = st.button("Sign In", type="primary", use_container_width=True)
        with c2:
            if st.button("Create Account", use_container_width=True, type="secondary"):
                st.session_state["auth_page"] = "register"
                st.session_state.pop("session_expired_message", None)
                st.rerun()

        if login_clicked:
            if not email.strip() or not password:
                st.error("Please fill in all fields.")
            else:
                with st.spinner("Signing in..."):
                    res = api_request("POST", "/api/auth/login", json={"email": email.strip(), "password": password})
                if "error" in res:
                    st.error(res["error"])
                else:
                    st.session_state["auth_token"] = res["access_token"]
                    st.session_state["user"] = res["user"]
                    st.session_state.pop("session_expired_message", None)
                    st.session_state.pop("auth_page", None)
                    for key in (
                        "cand_active_mock_id",
                        "active_interview_session_id",
                        "practice_feedback_cache",
                        "latest_resume_analysis",
                        "quick_match_res",
                        "selected_candidate_id",
                    ):
                        st.session_state.pop(key, None)
                    st.rerun()

def show_register():
    load_css()
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown(f"""
        <div style='text-align:center;margin-bottom:24px;margin-top:30px;'>
            <div class='sh-avatar' style='width:44px;height:44px;margin:0 auto 12px;background:var(--primary);'>{render_svg('sparkles', 22, '#ffffff')}</div>
            <h1 style='font-size:24px;font-weight:700;letter-spacing:-0.03em;'>SmartHire AI</h1>
            <div style='font-size:13px;color:var(--text-muted);'>Create your recruitment or candidate account</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<h3 style='font-size:16px;margin-bottom:14px;'>Create Account</h3>", unsafe_allow_html=True)

        full_name = st.text_input("Full Name *", placeholder="Jane Smith", key="reg_name")
        work_email = st.text_input("Email *", placeholder="jane@example.com", key="reg_email")

        job_title = st.selectbox("Role / Account Type", ROLES, key="reg_role")
        if job_title != "Candidate":
            company_name = st.text_input("Company Name *", placeholder="Acme Corp", key="reg_comp")
        else:
            company_name = "Candidate"

        phone = st.text_input("Phone (Optional)", placeholder="+1 555 000 0000", key="reg_phone")

        c1, c2 = st.columns(2)
        with c1:
            password = st.text_input("Password *", type="password", key="reg_pass")
        with c2:
            confirm_pass = st.text_input("Confirm Password *", type="password", key="reg_conf")

        cb1, cb2 = st.columns(2)
        with cb1:
            reg_clicked = st.button("Register", type="primary", use_container_width=True)
        with cb2:
            if st.button("Back to Sign In", use_container_width=True, type="secondary"):
                st.session_state["auth_page"] = "login"
                st.rerun()

        if reg_clicked:
            errors = []
            if not full_name.strip():
                errors.append("Full name is required.")
            if not work_email.strip():
                errors.append("Email is required.")
            if job_title != "Candidate" and not company_name.strip():
                errors.append("Company name is required.")
            if not password:
                errors.append("Password is required.")
            if password != confirm_pass:
                errors.append("Passwords do not match.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                payload = {
                    "full_name": full_name.strip(),
                    "email": work_email.strip().lower(),
                    "password": password,
                    "confirm_password": confirm_pass,
                    "company_name": company_name.strip(),
                    "job_title": job_title,
                    "phone_number": phone.strip() or None,
                }
                with st.spinner("Creating account..."):
                    res = api_request("POST", "/api/auth/register", json=payload)
                if "error" in res:
                    st.error(res["error"])
                else:
                    st.session_state["auth_token"] = res["access_token"]
                    st.session_state["user"] = res["user"]
                    st.session_state.pop("auth_page", None)
                    st.rerun()

# ---------------------------------------------------------------------------
# Main Router
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
