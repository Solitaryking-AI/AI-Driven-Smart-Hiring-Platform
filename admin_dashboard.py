"""
admin_dashboard.py — Standalone Admin Dashboard UI for SmartHire AI.

Exposes show_admin_dashboard(token, user) with complete administrative control:
- Command Center (system health overview and metric charts)
- Users & Access (user management, status/role modification, password reset)
- Recruiter Activity (activity audits per recruiter)
- Data Governance (duplicate candidate audits, scoped soft purges, restore)
- Jobs Oversight (job reassignment and status management)
- Audit Log (system security event viewer with CSV export)
- AI Usage Monitor (latency percentiles, error rates, feature calls)
- Platform Settings & Backup (feature flags, maintenance announcements, db backup download)
"""

import json
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ui_common import (
    api_request,
    _handle_unauthorized,
    render_svg,
    render_admin_topbar,
    get_plotly_layout,
    _esc,
)


# ---------------------------------------------------------------------------
# Navigation Sidebar & Shell Orchestrator
# ---------------------------------------------------------------------------

def show_admin_dashboard(token: str, user: dict):
    """Entry point for the dedicated Admin Control Plane."""
    user_role = str(user.get("job_title", "")).strip().lower()
    if user_role != "admin":
        st.error("Access forbidden: The Administration Dashboard is accessible exclusively to Administrator accounts.")
        st.stop()

    current_theme = st.session_state.get("theme", "dark")
    active_nav = st.session_state.get("admin_nav", "Command Center")

    # Fetch public platform settings to display maintenance notice if active
    pub_settings = api_request("GET", "/api/settings", token=token)
    if isinstance(pub_settings, dict) and pub_settings.get("maintenance_banner"):
        st.markdown(f"""
        <div style='background:rgba(239,68,68,0.15);border:1px solid #ef4444;color:#ef4444;padding:10px 16px;border-radius:8px;font-weight:600;margin-bottom:14px;display:flex;align-items:center;gap:8px;'>
            <span>⚠️ MAINTENANCE NOTICE:</span> {_esc(pub_settings['maintenance_banner'])}
        </div>
        """, unsafe_allow_html=True)


    with st.sidebar:
        st.markdown(f"""
        <div class='sh-brand-box' style='border-left:3px solid #6366f1;padding-left:8px;'>
            <div class='sh-avatar' style='width:34px;height:34px;background:#4f46e5;'>
                {render_svg('shield', 18, '#ffffff')}
            </div>
            <div>
                <div class='sh-brand-title' style='color:#818cf8;'>SmartHire Admin</div>
                <span class='sh-brand-badge' style='background:#4f46e5;color:#ffffff;font-weight:700;'>ADMIN</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        admin_name = _esc(user.get("full_name", "System Administrator"))
        admin_email = _esc(user.get("email", ""))
        st.markdown(f"""
        <div class='sh-card-sm' style='margin-bottom:14px;background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.2);'>
            <div style='font-size:13px;font-weight:700;color:var(--text-primary);'>{admin_name}</div>
            <div style='font-size:11px;color:#818cf8;'>{admin_email}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        # Group 1: OVERVIEW
        st.markdown("<div class='sh-nav-group-label' style='color:#818cf8;'>Overview</div>", unsafe_allow_html=True)
        if st.button(f"{'▸ ' if active_nav == 'Command Center' else '  '}Command Center", key="admin_nav_overview", use_container_width=True,
                     type="primary" if active_nav == "Command Center" else "secondary"):
            st.session_state["admin_nav"] = "Command Center"
            st.rerun()

        # Group 2: PEOPLE
        st.markdown("<div class='sh-nav-group-label' style='color:#818cf8;'>People & Access</div>", unsafe_allow_html=True)
        if st.button(f"{'▸ ' if active_nav == 'Users & Access' else '  '}Users & Access", key="admin_nav_users", use_container_width=True,
                     type="primary" if active_nav == "Users & Access" else "secondary"):
            st.session_state["admin_nav"] = "Users & Access"
            st.rerun()

        if st.button(f"{'▸ ' if active_nav == 'Recruiter Activity' else '  '}Recruiter Activity", key="admin_nav_rec_act", use_container_width=True,
                     type="primary" if active_nav == "Recruiter Activity" else "secondary"):
            st.session_state["admin_nav"] = "Recruiter Activity"
            st.rerun()

        # Group 3: DATA
        st.markdown("<div class='sh-nav-group-label' style='color:#818cf8;'>Data Governance</div>", unsafe_allow_html=True)
        if st.button(f"{'▸ ' if active_nav == 'Data Governance' else '  '}Data Governance", key="admin_nav_data_health", use_container_width=True,
                     type="primary" if active_nav == "Data Governance" else "secondary"):
            st.session_state["admin_nav"] = "Data Governance"
            st.rerun()

        if st.button(f"{'▸ ' if active_nav == 'Jobs Oversight' else '  '}Jobs Oversight", key="admin_nav_jobs", use_container_width=True,
                     type="primary" if active_nav == "Jobs Oversight" else "secondary"):
            st.session_state["admin_nav"] = "Jobs Oversight"
            st.rerun()

        # Group 4: SECURITY
        st.markdown("<div class='sh-nav-group-label' style='color:#818cf8;'>Security & Audit</div>", unsafe_allow_html=True)
        if st.button(f"{'▸ ' if active_nav == 'Audit Log' else '  '}Audit Log", key="admin_nav_audit", use_container_width=True,
                     type="primary" if active_nav == "Audit Log" else "secondary"):
            st.session_state["admin_nav"] = "Audit Log"
            st.rerun()

        # Group 5: AI TELEMETRY
        st.markdown("<div class='sh-nav-group-label' style='color:#818cf8;'>AI Telemetry</div>", unsafe_allow_html=True)
        if st.button(f"{'▸ ' if active_nav == 'AI Usage Monitor' else '  '}AI Usage Monitor", key="admin_nav_ai", use_container_width=True,
                     type="primary" if active_nav == "AI Usage Monitor" else "secondary"):
            st.session_state["admin_nav"] = "AI Usage Monitor"
            st.rerun()

        # Group 6: SYSTEM
        st.markdown("<div class='sh-nav-group-label' style='color:#818cf8;'>System Configuration</div>", unsafe_allow_html=True)
        if st.button(f"{'▸ ' if active_nav == 'Platform Settings & Backup' else '  '}Platform Settings & Backup", key="admin_nav_settings", use_container_width=True,
                     type="primary" if active_nav == "Platform Settings & Backup" else "secondary"):
            st.session_state["admin_nav"] = "Platform Settings & Backup"
            st.rerun()

        st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

        theme_text = "☀️ Light Mode" if current_theme == "dark" else "🌙 Dark Mode"
        if st.button(theme_text, key="admin_theme_toggle_btn", use_container_width=True, type="secondary"):
            st.session_state["theme"] = "light" if current_theme == "dark" else "dark"
            st.rerun()

        if st.button("Sign Out", key="admin_sign_out_btn", use_container_width=True, type="secondary"):
            theme = st.session_state.get("theme", "dark")
            st.session_state.clear()
            st.session_state["theme"] = theme
            st.rerun()

    # Dispatch to active view
    if active_nav == "Command Center":
        _show_command_center(token)
    elif active_nav == "Users & Access":
        _show_users_and_access(token, user)
    elif active_nav == "Recruiter Activity":
        _show_recruiter_activity(token)
    elif active_nav == "Data Governance":
        _show_data_governance(token)
    elif active_nav == "Jobs Oversight":
        _show_jobs_oversight(token)
    elif active_nav == "Audit Log":
        _show_audit_log(token)
    elif active_nav == "AI Usage Monitor":
        _show_ai_usage_monitor(token)
    elif active_nav == "Platform Settings & Backup":
        _show_platform_settings_and_backup(token)


# ---------------------------------------------------------------------------
# View 1: Command Center
# ---------------------------------------------------------------------------

def _show_command_center(token: str):
    render_admin_topbar(
        "Overview / Command Center",
        "Administrative Command Center",
        "Real-time operational metrics, infrastructure utilization, user growth, and AI telemetry."
    )

    data = api_request("GET", "/api/admin/overview", token=token)
    _handle_unauthorized(data)
    if "error" in data:
        st.error(f"Error loading system overview: {data['error']}")
        return

    # Metric Cards
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:#6366f1;'>{data.get('candidate_count', 0)}</div>
            <div class='sh-metric-lbl'>Active Candidates</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:#10b981;'>{data.get('active_users_7d', 0)} / {data.get('active_users_30d', 0)}</div>
            <div class='sh-metric-lbl'>Active Users (7d / 30d)</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:#3b82f6;'>{data.get('jobs_open', 0)} · {data.get('jobs_closed', 0)}</div>
            <div class='sh-metric-lbl'>Jobs (Open / Closed)</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:#ec4899;'>{data.get('ai_calls_7d', 0)}</div>
            <div class='sh-metric-lbl'>AI Calls 7d ({data.get('ai_error_rate_7d', 0)}% err)</div>
        </div>
        """, unsafe_allow_html=True)
    with c5:
        db_mb = round(data.get("db_file_size_bytes", 0) / (1024 * 1024), 2)
        up_mb = round(data.get("uploads_folder_size_bytes", 0) / (1024 * 1024), 2)
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:#f59e0b;'>{db_mb} MB</div>
            <div class='sh-metric-lbl'>DB Size ({up_mb} MB Uploads)</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # Visualizations
    chart_col1, chart_col2 = st.columns([1.6, 1])

    with chart_col1:
        st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Daily User Registrations (Last 30 Days)</h3>", unsafe_allow_html=True)
        signups_raw = data.get("signups_per_day_30d", [])
        if signups_raw:
            df_signups = pd.DataFrame(signups_raw)
            fig_signups = px.bar(
                df_signups,
                x="date",
                y="count",
                labels={"date": "Date", "count": "New Accounts"},
                color_discrete_sequence=["#6366f1"],
            )
            fig_signups.update_layout(**get_plotly_layout(st.session_state.get("theme", "dark")), height=280)
            st.plotly_chart(fig_signups, use_container_width=True)
        else:
            st.info("No registration data available in the current window.")

    with chart_col2:
        st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Registered User Role Distribution</h3>", unsafe_allow_html=True)
        role_counts = data.get("user_counts_by_role", {})
        if role_counts:
            df_roles = pd.DataFrame([{"Role": k, "Count": v} for k, v in role_counts.items() if v > 0])
            fig_roles = px.pie(
                df_roles,
                values="Count",
                names="Role",
                hole=0.55,
                color_discrete_sequence=["#10b981", "#3b82f6", "#6366f1", "#f59e0b"],
            )
            fig_roles.update_layout(**get_plotly_layout(st.session_state.get("theme", "dark")), height=280)
            st.plotly_chart(fig_roles, use_container_width=True)
        else:
            st.info("No role distribution data recorded.")


# ---------------------------------------------------------------------------
# View 2: Users & Access
# ---------------------------------------------------------------------------

def _show_users_and_access(token: str, current_admin: dict):
    render_admin_topbar(
        "People / Users & Access",
        "User Directory & Access Governance",
        "Manage account roles, deactivate credentials, provision users with temporary credentials, and enforce security policies."
    )

    # Search & Filter bar
    f1, f2, f3 = st.columns([2, 1, 1])
    with f1:
        search_q = st.text_input("Search Users", placeholder="Filter by full name or email address...", key="user_search_q")
    with f2:
        role_filter = st.selectbox("Role Filter", ["All", "Candidate", "Recruiter", "Admin"], key="user_role_filter")
    with f3:
        status_filter = st.selectbox("Status Filter", ["All", "Active", "Inactive"], key="user_status_filter")

    params = {}
    if search_q.strip():
        params["q"] = search_q.strip()
    if role_filter != "All":
        params["role"] = role_filter
    if status_filter != "All":
        params["status"] = status_filter.lower()

    users_res = api_request("GET", "/api/admin/users", token=token, params=params)
    _handle_unauthorized(users_res)
    users_list = users_res if isinstance(users_res, list) else []

    # Provision New User Form
    with st.expander("➕ Provision New Account with Temporary Credentials"):
        with st.form("form_create_user"):
            cu_col1, cu_col2 = st.columns(2)
            with cu_col1:
                nu_name = st.text_input("Full Name *", placeholder="Jane Doe")
                nu_email = st.text_input("Email Address *", placeholder="jane@example.com")
            with cu_col2:
                nu_role = st.selectbox("Platform Role *", ["Candidate", "Recruiter", "Admin"])
                nu_company = st.text_input("Company Organization", value="SmartHire")
            btn_create = st.form_submit_button("Provision User", type="primary")

            if btn_create:
                if not nu_name.strip() or not nu_email.strip():
                    st.error("Full Name and Email Address are required.")
                else:
                    payload = {
                        "full_name": nu_name.strip(),
                        "email": nu_email.strip(),
                        "job_title": nu_role,
                        "company_name": nu_company.strip(),
                    }
                    res_create = api_request("POST", "/api/admin/users", token=token, json=payload)
                    _handle_unauthorized(res_create)
                    if "error" in res_create:
                        st.error(res_create["error"])
                    else:
                        temp_pw = res_create.get("temp_password", "")
                        st.success(f"✓ User provisioned successfully! One-time Temporary Password: **`{temp_pw}`**")
                        st.info("Please share this temporary password securely with the user.")

    st.markdown(f"<div style='font-size:14px;font-weight:600;margin:16px 0 8px;'>Registered Directory ({len(users_list)} Accounts)</div>", unsafe_allow_html=True)

    if users_list:
        table_data = []
        for u in users_list:
            last_login = (u.get("last_login_at") or "Never")[:19]
            table_data.append({
                "ID": u.get("user_id"),
                "Name": u.get("full_name"),
                "Email": u.get("email"),
                "Role": u.get("job_title"),
                "Status": "Active" if u.get("is_active") else "Disabled",
                "Last Login": last_login,
                "Created": (u.get("created_at") or "")[:10],
            })
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
    else:
        st.info("No users match the search filters.")

    # Account Actions & Security Modifications
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Account Security & Status Management</h3>", unsafe_allow_html=True)
    st.caption("Apply status modifications, role adjustments, or initiate password resets. All changes are strictly audited.")

    if users_list:
        user_options = {f"#{u['user_id']} {u['full_name']} ({u['email']}) [Role: {u['job_title']}, Active: {u['is_active']}]": u for u in users_list}
        selected_label = st.selectbox("Select Target User Account", list(user_options.keys()), key="action_target_user")
        target_user = user_options[selected_label]

        act_col1, act_col2 = st.columns(2)
        tid = target_user['user_id']
        current_job_title = target_user.get("job_title", "Candidate")
        role_choices = ["Candidate", "Recruiter", "Admin"]
        role_index = role_choices.index(current_job_title) if current_job_title in role_choices else 0

        with act_col1:
            st.markdown(f"**Target ID:** #{tid} | **Email:** `{_esc(target_user['email'])}`")
            new_role = st.selectbox(
                "Modify Role",
                role_choices,
                index=role_index,
                key=f"mod_role_select_{tid}",
            )
            new_active = st.checkbox("Account Active", value=bool(target_user.get("is_active")), key=f"mod_active_check_{tid}")
            mod_reason = st.text_input("Audit Reason * (Required)", placeholder="Specify security or organizational justification...", key=f"mod_reason_input_{tid}")

            # Risky action typed confirmation
            is_risky = (new_active is False) or (target_user.get("job_title") == "Admin" and new_role != "Admin")
            if is_risky:
                st.warning("⚠️ Caution: You are attempting to deactivate an account or change an Admin's role.")
                confirm_type = st.text_input("Type 'CONFIRM' to authorize this modification:", key=f"risky_confirm_input_{tid}")
            else:
                confirm_type = "CONFIRM"

            if st.button("Apply Status / Role Changes", type="primary", key=f"btn_apply_user_mods_{tid}"):
                if not mod_reason.strip():
                    st.error("A non-empty audit reason is required for status or role modifications.")
                elif is_risky and confirm_type.strip() != "CONFIRM":
                    st.error("You must type 'CONFIRM' to authorize this risky change.")
                else:
                    patch_payload = {
                        "job_title": new_role,
                        "is_active": new_active,
                        "reason": mod_reason.strip(),
                    }
                    res_patch = api_request("PATCH", f"/api/admin/users/{tid}", token=token, json=patch_payload)
                    _handle_unauthorized(res_patch)
                    if "error" in res_patch:
                        st.error(res_patch["error"])
                    else:
                        st.toast(f"✓ Successfully updated account #{tid}.")
                        st.rerun()

        with act_col2:
            st.markdown("**Emergency Credential Management**")
            st.caption("Generate a randomized temporary password for the user. Old password will be immediately invalidated.")
            if st.button("Generate New Temporary Password", type="secondary", key=f"btn_reset_pw_user_{tid}"):
                res_pw = api_request("POST", f"/api/admin/users/{tid}/reset-password", token=token)
                _handle_unauthorized(res_pw)
                if "error" in res_pw:
                    st.error(res_pw["error"])
                else:
                    new_temp = res_pw.get("temp_password", "")
                    st.success(f"✓ Password reset! One-time Temporary Password: **`{new_temp}`**")



# ---------------------------------------------------------------------------
# View 3: Recruiter Activity
# ---------------------------------------------------------------------------

def _show_recruiter_activity(token: str):
    render_admin_topbar(
        "People / Recruiter Activity",
        "Recruiter Activity & Output Metrics",
        "Audit recruiter engagement, open job requisitions, candidate pipeline uploads, and mock interview workloads."
    )

    data = api_request("GET", "/api/admin/recruiters/activity", token=token)
    _handle_unauthorized(data)
    if "error" in data:
        st.error(f"Error fetching recruiter activity: {data['error']}")
        return

    recruiters = data if isinstance(data, list) else []

    total_rec = len(recruiters)
    total_jobs = sum(r.get("jobs_created", 0) for r in recruiters)
    total_interviews = sum(r.get("interviews_created", 0) for r in recruiters)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:#6366f1;'>{total_rec}</div>
            <div class='sh-metric-lbl'>Total Recruiters</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:#10b981;'>{total_jobs}</div>
            <div class='sh-metric-lbl'>Total Requisitions Posted</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:#3b82f6;'>{total_interviews}</div>
            <div class='sh-metric-lbl'>Interview Sessions Conducted</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
    st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Recruiter Audit Breakdown</h3>", unsafe_allow_html=True)

    if recruiters:
        table_rows = []
        for r in recruiters:
            table_rows.append({
                "Recruiter Name": r.get("full_name"),
                "Email": r.get("email"),
                "Jobs Created": r.get("jobs_created", 0),
                "Interviews Created": r.get("interviews_created", 0),
                "Candidates Uploaded": r.get("candidates_uploaded", 0),
                "Last Login": (r.get("last_login_at") or "Never")[:19],
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No active recruiter accounts registered.")


# ---------------------------------------------------------------------------
# View 4: Data Governance
# ---------------------------------------------------------------------------

def _show_data_governance(token: str):
    render_admin_topbar(
        "Data / Governance",
        "Data Governance, Quality Diagnostics & Retention",
        "Identify candidate anomalies, orphan resume files, run confirmed soft-purges, and restore archived records."
    )

    data = api_request("GET", "/api/admin/data-health", token=token)
    _handle_unauthorized(data)
    if "error" in data:
        st.error(f"Error fetching data diagnostics: {data['error']}")
        return

    # Section 1: Health Diagnostics
    st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Repository Diagnostic Findings</h3>", unsafe_allow_html=True)
    d1, d2, d3, d4 = st.columns(4)

    dup_list = data.get("duplicate_candidates", [])
    empty_skills = data.get("empty_skills_candidates", [])
    unref_files = data.get("unreferenced_upload_files", [])
    missing_files = data.get("missing_resume_files", [])

    with d1:
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:{'#ef4444' if dup_list else '#10b981'};'>{len(dup_list)}</div>
            <div class='sh-metric-lbl'>Duplicate Email Groups</div>
        </div>
        """, unsafe_allow_html=True)
    with d2:
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:{'#f59e0b' if empty_skills else '#10b981'};'>{len(empty_skills)}</div>
            <div class='sh-metric-lbl'>Candidates with Empty Skills</div>
        </div>
        """, unsafe_allow_html=True)
    with d3:
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:{'#f59e0b' if unref_files else '#10b981'};'>{len(unref_files)}</div>
            <div class='sh-metric-lbl'>Orphan Files in uploads/</div>
        </div>
        """, unsafe_allow_html=True)
    with d4:
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:{'#ef4444' if missing_files else '#10b981'};'>{len(missing_files)}</div>
            <div class='sh-metric-lbl'>Missing Disk Resumes</div>
        </div>
        """, unsafe_allow_html=True)

    tab_dup, tab_skills, tab_orphan, tab_missing = st.tabs([
        f"Duplicates ({len(dup_list)})",
        f"Empty Skills ({len(empty_skills)})",
        f"Orphan Files ({len(unref_files)})",
        f"Missing Files ({len(missing_files)})",
    ])

    with tab_dup:
        if dup_list:
            st.dataframe(pd.DataFrame(dup_list), use_container_width=True, hide_index=True)
        else:
            st.success("✓ No duplicate candidate email entries found.")

    with tab_skills:
        if empty_skills:
            st.dataframe(pd.DataFrame(empty_skills), use_container_width=True, hide_index=True)
        else:
            st.success("✓ All candidate profiles contain parsed technical skills.")

    with tab_orphan:
        if unref_files:
            st.write("Files stored in `uploads/` not mapped to any active candidate resume path:")
            st.dataframe(pd.DataFrame({"Orphan File": unref_files}), use_container_width=True, hide_index=True)
        else:
            st.success("✓ No orphan files detected in `uploads/`.")

    with tab_missing:
        if missing_files:
            st.dataframe(pd.DataFrame(missing_files), use_container_width=True, hide_index=True)
        else:
            st.success("✓ All candidate resume files verified on disk.")

    # Section 2: Scoped Purge with Typed Confirmation
    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
    st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Retention Policy: Scoped Candidate Soft-Purge</h3>", unsafe_allow_html=True)
    st.caption("Soft-deletes candidate records based on age or stage criteria. Purged records are preserved in the DB for auditability and can be restored.")

    with st.form("form_scoped_purge"):
        p_c1, p_c2 = st.columns(2)
        with p_c1:
            purge_days = st.number_input("Records Older Than (Days)", min_value=0, max_value=3650, value=90)
        with p_c2:
            purge_stage = st.selectbox("Stage Scope", ["All Stages", "new", "shortlisted", "interview", "offered", "hired", "rejected"])

        st.caption("To prevent accidental data loss, execute a trial preview first or supply the exact typed confirmation phrase.")
        confirm_input = st.text_input("Typed Confirmation (e.g. 'PURGE X RECORDS')", placeholder="Enter required confirmation text...")

        col_b1, col_b2 = st.columns([1, 1])
        with col_b1:
            btn_check = st.form_submit_button("Preview Matching Records (Trial)", type="secondary")
        with col_b2:
            btn_purge = st.form_submit_button("Execute Scoped Soft-Purge", type="primary")

        if btn_check:
            stage_val = None if purge_stage == "All Stages" else purge_stage
            payload = {
                "older_than_days": int(purge_days) if purge_days > 0 else None,
                "stage": stage_val,
                "confirm_text": "PREVIEW_TRIAL",
            }
            res_trial = api_request("POST", "/api/admin/candidates/purge", token=token, json=payload)
            _handle_unauthorized(res_trial)
            err = res_trial.get("error", {})
            if isinstance(err, str) and err.startswith("{"):
                try:
                    err = json.loads(err)
                except Exception:
                    pass
            if isinstance(err, dict):
                matched = err.get("matched_count", 0)
                expected = err.get("expected_confirm", f"PURGE {matched} RECORDS")
                if matched == 0:
                    st.info("ℹ️ No candidate records match the selected criteria.")
                else:
                    st.warning(
                        f"Found **{matched}** candidate record(s) matching your criteria.\n\n"
                        f"To execute this purge, enter **`{expected}`** in the confirmation box above and click **Execute Scoped Soft-Purge**."
                    )
            else:
                st.info(f"Check result: {err}")

        if btn_purge:
            stage_val = None if purge_stage == "All Stages" else purge_stage
            payload = {
                "older_than_days": int(purge_days) if purge_days > 0 else None,
                "stage": stage_val,
                "confirm_text": confirm_input.strip(),
            }
            res_purge = api_request("POST", "/api/admin/candidates/purge", token=token, json=payload)
            _handle_unauthorized(res_purge)
            if "error" in res_purge:
                err = res_purge["error"]
                if isinstance(err, str) and err.startswith("{"):
                    try:
                        err = json.loads(err)
                    except Exception:
                        pass
                if isinstance(err, dict):
                    matched = err.get("matched_count", 0)
                    expected = err.get("expected_confirm", f"PURGE {matched} RECORDS")
                    if matched == 0:
                        st.info("ℹ️ No candidate records match the selected criteria.")
                    else:
                        st.error(
                            f"**Confirmation Mismatch**: Found **{matched}** candidate record(s) matching criteria.\n\n"
                            f"Please type exact phrase: **`{expected}`** in the confirmation box above to proceed."
                        )
                else:
                    st.error(f"Purge rejected: {err}")
            else:
                st.success(f"✓ {res_purge.get('message', 'Purge completed successfully.')}")
                st.rerun()

    # Section 3: Restore Candidate
    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
    st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Restore Archived Candidate</h3>", unsafe_allow_html=True)
    r_col1, r_col2 = st.columns([2, 1])
    with r_col1:
        restore_id = st.number_input("Candidate ID to Restore", min_value=1, step=1, key="input_restore_cand_id")
    with r_col2:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("Restore Candidate", type="secondary", key="btn_restore_cand"):
            res_rest = api_request("POST", f"/api/admin/candidates/{int(restore_id)}/restore", token=token)
            _handle_unauthorized(res_rest)
            if "error" in res_rest:
                st.error(res_rest["error"])
            else:
                st.success(f"✓ Candidate #{restore_id} ({res_rest.get('name', 'Candidate')}) restored successfully!")


# ---------------------------------------------------------------------------
# View 5: Jobs Oversight
# ---------------------------------------------------------------------------

def _show_jobs_oversight(token: str):
    render_admin_topbar(
        "Data / Jobs Oversight",
        "Job Requisitions Governance & Reassignment",
        "Audit organizational job requisitions, reassign ownership across recruiting personnel, and adjust job statuses."
    )

    jobs_data = api_request("GET", "/api/admin/jobs", token=token)
    _handle_unauthorized(jobs_data)
    if "error" in jobs_data:
        st.error(f"Error loading jobs: {jobs_data['error']}")
        return

    jobs_list = jobs_data if isinstance(jobs_data, list) else []

    # Fetch recruiters for reassignment dropdown
    rec_res = api_request("GET", "/api/admin/users?role=Recruiter", token=token)
    _handle_unauthorized(rec_res)
    recruiters = rec_res if isinstance(rec_res, list) else []
    rec_options = {f"{r['full_name']} ({r['email']})": r["user_id"] for r in recruiters}

    st.markdown(f"<div style='font-size:14px;font-weight:600;margin-bottom:8px;'>All Requisitions ({len(jobs_list)} Jobs)</div>", unsafe_allow_html=True)

    if jobs_list:
        table_rows = []
        for j in jobs_list:
            table_rows.append({
                "Job ID": j.get("job_id"),
                "Title": j.get("title"),
                "Department": j.get("department") or "General",
                "Status": str(j.get("status", "open")).upper(),
                "Owner": j.get("owner_name") or "Unassigned",
                "Owner Email": j.get("owner_email") or "-",
                "Created": (j.get("created_at") or "")[:10],
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Reassign Requisition or Update Status</h3>", unsafe_allow_html=True)

        job_opts = {f"#{j['job_id']}: {j['title']} (Owner: {j.get('owner_name') or 'Unassigned'})": j for j in jobs_list}
        selected_job_label = st.selectbox("Select Requisition", list(job_opts.keys()))
        target_job = job_opts[selected_job_label]

        j_col1, j_col2 = st.columns(2)
        with j_col1:
            target_owner_label = st.selectbox("Reassign Owner", list(rec_options.keys()) if rec_options else ["No Recruiters Available"])
            new_owner_id = rec_options.get(target_owner_label)
        with j_col2:
            new_status = st.selectbox(
                "Job Status",
                ["open", "closed"],
                index=0 if str(target_job.get("status")).lower() == "open" else 1,
            )

        if st.button("Apply Job Requisition Updates", type="primary"):
            patch_body = {"status": new_status}
            if new_owner_id:
                patch_body["created_by"] = new_owner_id

            res_j_patch = api_request("PATCH", f"/api/admin/jobs/{target_job['job_id']}", token=token, json=patch_body)
            _handle_unauthorized(res_j_patch)
            if "error" in res_j_patch:
                st.error(res_j_patch["error"])
            else:
                st.success(f"✓ Job requisition #{target_job['job_id']} updated successfully.")
                st.rerun()
    else:
        st.info("No job requisitions created yet.")


# ---------------------------------------------------------------------------
# View 6: Audit Log
# ---------------------------------------------------------------------------

def _show_audit_log(token: str):
    render_admin_topbar(
        "Security / Audit Log",
        "System Security & Administrative Audit Trail",
        "Inspect verified audit rows covering security events, role modifications, purges, and system configurations."
    )

    # Filters
    c1, c2, c3 = st.columns([1.5, 1.5, 1])
    with c1:
        f_actor = st.text_input("Filter by Actor Email", placeholder="actor@smarthire.local", key="audit_filter_actor")
    with c2:
        action_choices = [
            "All Actions",
            "update_user",
            "create_user",
            "reset_password",
            "purge_candidates",
            "restore_candidate",
            "delete_candidate",
            "update_job",
            "update_settings",
            "backup_database",
            "login_success",
            "login_failure",
            "register_success",
        ]
        f_action = st.selectbox("Filter by Action Type", action_choices, key="audit_filter_action")
    with c3:
        f_limit = st.selectbox("Log Limit", [50, 100, 200, 500], index=1, key="audit_filter_limit")

    params = {"limit": f_limit}
    if f_actor.strip():
        params["actor_email"] = f_actor.strip()
    if f_action != "All Actions":
        params["action"] = f_action

    logs_res = api_request("GET", "/api/admin/audit-logs", token=token, params=params)
    _handle_unauthorized(logs_res)
    logs_list = logs_res if isinstance(logs_res, list) else []

    # CSV Download (On-Demand Preparation)
    if "admin_audit_csv" not in st.session_state:
        st.session_state["admin_audit_csv"] = None

    c_btn1, c_btn2 = st.columns([1.5, 2])
    with c_btn1:
        if st.button("Prepare Audit CSV Export", key="btn_prep_audit_csv", type="secondary"):
            with st.spinner("Preparing CSV export..."):
                csv_resp = api_request("GET", "/api/admin/audit-logs?format=csv", token=token, params=params)
                _handle_unauthorized(csv_resp)
                csv_content = ""
                if isinstance(csv_resp, dict) and "content" in csv_resp:
                    csv_content = csv_resp["content"]
                elif isinstance(csv_resp, dict) and "text" in csv_resp:
                    csv_content = csv_resp["text"]
                st.session_state["admin_audit_csv"] = csv_content
                st.rerun()

    if st.session_state["admin_audit_csv"]:
        with c_btn2:
            st.download_button(
                label="📥 Download Filtered Audit Logs (CSV)",
                data=st.session_state["admin_audit_csv"],
                file_name="smarthire_audit_logs.csv",
                mime="text/csv",
                type="primary",
            )


    st.markdown(f"<div style='font-size:14px;font-weight:600;margin:16px 0 8px;'>Audit Event Trail ({len(logs_list)} Events)</div>", unsafe_allow_html=True)

    if logs_list:
        table_rows = []
        for l in logs_list:
            table_rows.append({
                "Audit ID": l.get("audit_id"),
                "Timestamp": (l.get("created_at") or "")[:19].replace("T", " "),
                "Actor Email": l.get("actor_email") or "System",
                "Action": l.get("action"),
                "Target": f"{l.get('target_type') or '-'}:{l.get('target_id') or '-'}",
                "Details": (l.get("details") or "")[:120],
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No audit events match the specified filter criteria.")


# ---------------------------------------------------------------------------
# View 7: AI Usage Monitor
# ---------------------------------------------------------------------------

def _show_ai_usage_monitor(token: str):
    render_admin_topbar(
        "AI / Telemetry",
        "LLM Telemetry, Latency & Cost Optimization",
        "Monitor AI model response latencies, request volumes per feature, error rates, and top consuming accounts."
    )

    window_days = st.radio("Telemetry Time Window", [7, 14, 30], index=0, horizontal=True)

    ai_data = api_request("GET", f"/api/admin/ai-usage?days={window_days}", token=token)
    _handle_unauthorized(ai_data)
    if "error" in ai_data:
        st.error(f"Error fetching AI usage telemetry: {ai_data['error']}")
        return

    # Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:#6366f1;'>{ai_data.get('total_calls', 0)}</div>
            <div class='sh-metric-lbl'>Total LLM Invocations ({window_days}d)</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:#10b981;'>{ai_data.get('p50_latency_ms', 0)} ms</div>
            <div class='sh-metric-lbl'>P50 Latency (Median)</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:#f59e0b;'>{ai_data.get('p95_latency_ms', 0)} ms</div>
            <div class='sh-metric-lbl'>P95 Latency (95th %ile)</div>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class='sh-metric-card'>
            <div class='sh-metric-num' style='color:{'#ef4444' if ai_data.get('error_rate', 0) > 5 else '#3b82f6'};'>{ai_data.get('error_rate', 0)}%</div>
            <div class='sh-metric-lbl'>Error Rate</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # Charts Row
    c_col1, c_col2 = st.columns([1.4, 1])
    with c_col1:
        st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Daily AI Invocations Trend</h3>", unsafe_allow_html=True)
        series_data = ai_data.get("daily_series", [])
        if series_data:
            df_series = pd.DataFrame(series_data)
            fig_daily = px.line(
                df_series,
                x="date",
                y="calls",
                labels={"date": "Date", "calls": "Invocations"},
                color_discrete_sequence=["#6366f1"],
                markers=True,
            )
            fig_daily.update_layout(**get_plotly_layout(st.session_state.get("theme", "dark")), height=260)
            st.plotly_chart(fig_daily, use_container_width=True)
        else:
            st.info("No daily series data available.")

    with c_col2:
        st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Invocations by AI Capability</h3>", unsafe_allow_html=True)
        feature_calls = ai_data.get("calls_per_feature", {})
        if feature_calls:
            df_feat = pd.DataFrame([{"Feature": k, "Calls": v} for k, v in feature_calls.items()])
            fig_feat = px.pie(
                df_feat,
                values="Calls",
                names="Feature",
                hole=0.5,
                color_discrete_sequence=["#6366f1", "#10b981", "#3b82f6", "#ec4899", "#f59e0b"],
            )
            fig_feat.update_layout(**get_plotly_layout(st.session_state.get("theme", "dark")), height=260)
            st.plotly_chart(fig_feat, use_container_width=True)
        else:
            st.info("No feature call breakdown recorded.")

    # Top 10 Consuming Users
    st.markdown("<h3 style='font-size:16px;margin:16px 0 8px;'>Top 10 Active AI Consumers</h3>", unsafe_allow_html=True)
    top_users = ai_data.get("top_10_users", [])
    if top_users:
        st.dataframe(pd.DataFrame(top_users), use_container_width=True, hide_index=True)
    else:
        st.info("No user-attributed AI calls in this timeframe.")


# ---------------------------------------------------------------------------
# View 8: Platform Settings & Backup
# ---------------------------------------------------------------------------

def _show_platform_settings_and_backup(token: str):
    render_admin_topbar(
        "System / Configuration",
        "Platform Feature Toggles & Database Backup",
        "Control global feature availability, publish platform maintenance announcements, and download database backups."
    )

    settings_res = api_request("GET", "/api/admin/settings", token=token)
    _handle_unauthorized(settings_res)
    if "error" in settings_res:
        st.error(f"Error loading platform settings: {settings_res['error']}")
        return

    curr_settings = settings_res.get("settings", {})

    # Feature Toggles Form
    st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Platform Feature Toggles</h3>", unsafe_allow_html=True)
    st.caption("Instantly enable or disable capabilities platform-wide. Changes take effect on next request.")

    with st.form("form_platform_settings"):
        t1, t2 = st.columns(2)
        with t1:
            f_reg = st.toggle("Public Candidate Registration", value=(curr_settings.get("registration_open", "true") == "true"))
            f_mock = st.toggle("AI Mock Interview Live Room", value=(curr_settings.get("feature_mock_interview", "true") == "true"))
            f_voice = st.toggle("Voice Speech-to-Text & Audio Capture", value=(curr_settings.get("feature_voice", "true") == "true"))
        with t2:
            f_resume = st.toggle("AI Resume Intelligence & ATS Scoring", value=(curr_settings.get("feature_resume_ai", "true") == "true"))
            f_practice = st.toggle("Candidate Practice Assessments", value=(curr_settings.get("feature_practice", "true") == "true"))

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        st.markdown("**Maintenance & Announcement Banner**")
        st.caption("Displays an urgent announcement banner across all dashboards (leave blank to dismiss).")
        m_banner = st.text_input("Banner Announcement Message", value=curr_settings.get("maintenance_banner", ""))

        btn_save = st.form_submit_button("Save Platform Configuration", type="primary")
        if btn_save:
            payload = {
                "settings": {
                    "registration_open": "true" if f_reg else "false",
                    "feature_mock_interview": "true" if f_mock else "false",
                    "feature_voice": "true" if f_voice else "false",
                    "feature_resume_ai": "true" if f_resume else "false",
                    "feature_practice": "true" if f_practice else "false",
                    "maintenance_banner": m_banner.strip(),
                }
            }
            save_res = api_request("PUT", "/api/admin/settings", token=token, json=payload)
            _handle_unauthorized(save_res)
            if "error" in save_res:
                st.error(save_res["error"])
            else:
                st.toast("✓ Platform configuration updated successfully.")
                st.rerun()

    # Section: Database Backup (On-Demand Preparation)
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Database Backup & Recovery</h3>", unsafe_allow_html=True)
    st.caption("Generate a secure download copy of `smarthire.db`. Every backup download is registered in the immutable audit log.")

    if "admin_backup_bytes" not in st.session_state:
        st.session_state["admin_backup_bytes"] = None

    b_col1, b_col2 = st.columns([1.5, 2])
    with b_col1:
        if st.button("Prepare Database Backup", key="btn_prep_backup", type="secondary"):
            with st.spinner("Generating database snapshot..."):
                backup_resp = api_request("GET", "/api/admin/backup", token=token)
                _handle_unauthorized(backup_resp)
                if isinstance(backup_resp, dict) and "content" in backup_resp:
                    st.session_state["admin_backup_bytes"] = backup_resp["content"]
                    st.rerun()
                else:
                    err = backup_resp.get("error", "Failed to generate backup.") if isinstance(backup_resp, dict) else "Failed."
                    st.error(err)

    if st.session_state["admin_backup_bytes"] is not None:
        with b_col2:
            st.download_button(
                label="💾 Download SQLite Database Backup",
                data=st.session_state["admin_backup_bytes"],
                file_name="smarthire_backup.db",
                mime="application/octet-stream",
                type="primary",
                key="btn_download_db_backup",
            )

