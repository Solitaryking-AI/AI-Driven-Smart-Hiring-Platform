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
        "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
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


def render_profile_page(token: str, user: dict, role_label: str):
    """
    Render a clean, reactive profile management view for Recruiter and Admin roles.
    Allows viewing immutable account attributes (email, role, created_at, last_login_at)
    and modifying editable attributes (full_name, phone_number, company_name)
    with auditing and optional password change accordion.
    """
    role_color = "#818cf8" if role_label.lower() == "admin" else "var(--primary)"

    st.markdown(f"""
    <div class='sh-page-header'>
        <div class='sh-breadcrumb' style='margin-bottom:8px;'>
            {render_svg('user', 14, role_color)}
            <span>SmartHire AI</span>
            <span>/</span>
            <strong>My Profile</strong>
        </div>
        <h1 class='sh-title'>My Profile</h1>
        <div class='sh-subtitle'>Manage your personal account details, organization, and security preferences.</div>
    </div>
    """, unsafe_allow_html=True)

    # 1. Fetch fresh profile data from backend
    profile_data = api_request("GET", "/api/auth/profile", token=token)
    if isinstance(profile_data, dict) and profile_data.get("__unauthorized"):
        _handle_unauthorized(profile_data)
        return
    if isinstance(profile_data, dict) and ("error" in profile_data or "detail" in profile_data):
        st.error(format_error_detail(profile_data.get("error") or profile_data.get("detail")))
        return

    # Use fetched profile or fallback to session user
    p = profile_data if isinstance(profile_data, dict) and "email" in profile_data else user

    # 2. Account Overview Card (Read-Only)
    st.markdown("<h3 style='font-size:16px;margin-bottom:12px;'>Account Information</h3>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class='sh-card-sm'>
            <div style='font-size:11px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;'>Email Address</div>
            <div style='font-size:13px;font-weight:600;color:var(--text-primary);margin-top:4px;'>{_esc(p.get('email', '-'))}</div>
            <div style='font-size:10px;color:var(--text-subtle);margin-top:2px;'>Read-only system identifier</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class='sh-card-sm'>
            <div style='font-size:11px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;'>Assigned Role</div>
            <div style='font-size:13px;font-weight:600;color:{role_color};margin-top:4px;'>{_esc(p.get('job_title', role_label))}</div>
            <div style='font-size:10px;color:var(--text-subtle);margin-top:2px;'>Governed by Administrator</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        created_str = str(p.get('created_at', '-'))[:10] if p.get('created_at') else '-'
        st.markdown(f"""
        <div class='sh-card-sm'>
            <div style='font-size:11px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;'>Account Created</div>
            <div style='font-size:13px;font-weight:600;color:var(--text-primary);margin-top:4px;'>{_esc(created_str)}</div>
            <div style='font-size:10px;color:var(--text-subtle);margin-top:2px;'>Registration timestamp</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        login_str = str(p.get('last_login_at', '-'))[:16].replace('T', ' ') if p.get('last_login_at') else 'Active Session'
        st.markdown(f"""
        <div class='sh-card-sm'>
            <div style='font-size:11px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;'>Last Login</div>
            <div style='font-size:13px;font-weight:600;color:var(--text-primary);margin-top:4px;'>{_esc(login_str)}</div>
            <div style='font-size:10px;color:var(--text-subtle);margin-top:2px;'>UTC timestamp</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # 3. Editable Profile Form
    st.markdown("<h3 style='font-size:16px;margin-bottom:12px;'>Edit Profile Details</h3>", unsafe_allow_html=True)
    with st.form("form_edit_user_profile"):
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            full_name = st.text_input("Full Name *", value=p.get("full_name") or "", key="profile_edit_name")
            company_name = st.text_input("Company / Organization *", value=p.get("company_name") or "", key="profile_edit_company")
        with f_col2:
            phone_number = st.text_input("Phone Number", value=p.get("phone_number") or "", placeholder="+1 (555) 000-0000", key="profile_edit_phone")
            st.caption("Phone number accepts digits, spaces, and formatting characters (+ - ( )). Leave blank to remove.")

        save_profile_btn = st.form_submit_button("Save Profile Changes", type="primary")

        if save_profile_btn:
            name_clean = full_name.strip()
            comp_clean = company_name.strip()
            phone_clean = phone_number.strip() if phone_number else ""

            if not name_clean:
                st.error("Full name cannot be blank.")
            elif not comp_clean:
                st.error("Company / Organization cannot be blank.")
            else:
                update_payload = {
                    "full_name": name_clean,
                    "company_name": comp_clean,
                    "phone_number": phone_clean if phone_clean else None,
                }
                save_res = api_request("PUT", "/api/auth/profile", token=token, json=update_payload)
                if isinstance(save_res, dict) and save_res.get("__unauthorized"):
                    _handle_unauthorized(save_res)
                    return
                if isinstance(save_res, dict) and ("error" in save_res or "detail" in save_res):
                    st.error(format_error_detail(save_res.get("error") or save_res.get("detail")))
                elif isinstance(save_res, dict) and "user_id" in save_res:
                    st.session_state["user"] = save_res
                    st.toast("Profile updated successfully!", icon="✅")
                    st.rerun()
                else:
                    st.error("Failed to update profile. Please try again.")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # 4. Security: Change Password Accordion
    with st.expander("Security Preferences: Change Password", expanded=False):
        st.caption("Update your account password. Must be at least 8 characters long and no longer than 72 bytes.")
        with st.form("form_change_user_password"):
            curr_pass = st.text_input("Current Password *", type="password", key="profile_change_curr_pass")
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                new_pass = st.text_input("New Password *", type="password", key="profile_change_new_pass")
            with p_col2:
                conf_pass = st.text_input("Confirm New Password *", type="password", key="profile_change_conf_pass")

            change_pass_btn = st.form_submit_button("Update Password", type="secondary")

            if change_pass_btn:
                if not curr_pass or not new_pass or not conf_pass:
                    st.error("Please fill in all password fields.")
                elif new_pass != conf_pass:
                    st.error("New passwords do not match.")
                elif len(new_pass.encode("utf-8")) > 72:
                    st.error("Password cannot exceed 72 bytes.")
                elif len(new_pass) < 8:
                    st.error("Password must be at least 8 characters long.")
                else:
                    pwd_payload = {
                        "current_password": curr_pass,
                        "new_password": new_pass,
                        "confirm_password": conf_pass,
                    }
                    pwd_res = api_request("POST", "/api/auth/change-password", token=token, json=pwd_payload)
                    if isinstance(pwd_res, dict) and pwd_res.get("__unauthorized"):
                        _handle_unauthorized(pwd_res)
                        return
                    if isinstance(pwd_res, dict) and ("error" in pwd_res or "detail" in pwd_res):
                        st.error(format_error_detail(pwd_res.get("error") or pwd_res.get("detail")))
                    else:
                        st.success("✓ Password changed successfully.")
                        st.toast("Password updated successfully!", icon="🔒")


