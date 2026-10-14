"""
ui_common.py — Shared frontend utilities for SmartHire AI.

Provides reusable HTTP request handling, session authentication handlers,
SVG icons, Plotly chart layout styling, and topbar components for both
recruiter and admin dashboards.
"""

import html
import os
from typing import Any, Optional
import requests
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")

_HTTP_SESSION = requests.Session()
_http_adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=50, max_retries=1)
_HTTP_SESSION.mount("http://", _http_adapter)
_HTTP_SESSION.mount("https://", _http_adapter)


def _esc(val: Any) -> str:
    """Escape dynamic strings for safe interpolation in raw HTML markdown."""
    if val is None:
        return ""
    return html.escape(str(val))


def format_error_detail(detail: Any) -> str:
    """Format FastAPI error detail (str, list of dicts, or other) into clean human-readable text."""
    if detail is None:
        return "An unexpected error occurred."
    if isinstance(detail, dict):
        return str(detail.get("detail") or detail.get("error") or detail.get("message") or detail)
    if isinstance(detail, list):
        messages = []
        for item in detail:
            if isinstance(item, dict):
                loc = " -> ".join(str(l) for l in item.get("loc", []) if l != "body")
                msg = item.get("msg", "")
                if loc and msg:
                    messages.append(f"{loc}: {msg}")
                elif msg:
                    messages.append(msg)
                else:
                    messages.append(str(item))
            else:
                messages.append(str(item))
        return "\n".join(messages) if messages else "Validation error occurred."
    return str(detail)


def api_request(method: str, endpoint: str, token: str = None, **kwargs):
    """Make an authenticated or unauthenticated HTTP request to the FastAPI backend."""
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
                return {"error": format_error_detail(detail)}
            return {"error": "Session expired. Please log in again.", "__unauthorized": True}
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            return {"error": format_error_detail(detail)}
        try:
            return resp.json()
        except Exception:
            return {"success": True, "content": resp.content, "text": resp.text, "headers": dict(resp.headers)}
    except requests.exceptions.ConnectionError:
        return {"error": f"Cannot connect to backend. Make sure FastAPI is running on {API_BASE_URL}"}
    except Exception as e:
        return {"error": str(e)}


def _handle_unauthorized(res: dict):
    """Detect expired JWT tokens and trigger graceful session state cleanup and rerun."""
    if isinstance(res, dict) and res.get("__unauthorized"):
        theme = st.session_state.get("theme", "dark")
        st.session_state.clear()
        st.session_state["theme"] = theme
        st.session_state["session_expired_message"] = "Session expired. Please log in again."
        st.rerun()


def render_svg(icon_name: str, size: int = 18, color: str = "currentColor") -> str:
    """Render inline SVG icons."""
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
        "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
        "activity": '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
        "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3"/>',
        "cpu": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>',
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


def get_plotly_layout(theme: str = "dark"):
    """Return responsive Plotly theme layout configurations."""
    is_dark = (theme == "dark")
    font_color = "#F8FAFC" if is_dark else "#0F172A"
    grid_color = "rgba(255,255,255,0.08)" if is_dark else "rgba(15, 23, 42, 0.06)"
    bg_color = "rgba(0,0,0,0)"
    return {
        "template": "plotly_dark" if is_dark else "plotly_white",
        "plot_bgcolor": bg_color,
        "paper_bgcolor": bg_color,
        "font": dict(family="Inter", color=font_color, size=12),
        "xaxis_gridcolor": grid_color,
        "yaxis_gridcolor": grid_color,
    }


def _theme_primary() -> str:
    return "#6366F1" if st.session_state.get("theme", "dark") == "dark" else "#2563EB"


def render_admin_topbar(breadcrumb: str, title: str, subtitle: str):
    """Render topbar header for the Admin Control Plane."""
    b_esc = _esc(breadcrumb)
    t_esc = _esc(title)
    s_esc = _esc(subtitle)
    st.markdown(f"""
    <div class='sh-topbar' style='border-bottom:1px solid rgba(99,102,241,0.25);'>
        <div class='sh-breadcrumb'>
            {render_svg('shield', 14, '#6366F1')}
            <span>SmartHire AI</span>
            <span>/</span>
            <span style='color:#818cf8;font-weight:600;'>Administration</span>
            <span>/</span>
            <strong>{b_esc}</strong>
        </div>
        <div style='display:flex;align-items:center;gap:12px;'>
            <span class='sh-stat-pill' style='background:rgba(99,102,241,0.15);color:#818cf8;border:1px solid rgba(99,102,241,0.3);font-weight:700;'>
                CONTROL PLANE v3.0
            </span>
        </div>
    </div>
    <div class='sh-page-header'>
        <h1 class='sh-title' style='color:var(--text-primary);'>{t_esc}</h1>
        <div class='sh-subtitle'>{s_esc}</div>
    </div>
    """, unsafe_allow_html=True)

