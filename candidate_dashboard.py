"""
candidate_dashboard.py — Standalone Graphical Dashboard for Candidate Portal in SmartHire AI.

Exposes show_candidate_overview_dashboard(token, user, profile) providing:
- Career Readiness Score gauge (composite weighted indicator)
- Key Performance Indicator metrics (completeness, ATS, practice, mock, skills)
- Profile Completeness breakdown & missing element alerts
- Mock Interview Competency Radar
- Practice Score Trend & Question Type distribution
- ATS Score Trajectory & Resume optimization insights
- Open Job Requisition Fit ranking with matched/missing skill tags
- Chronological Activity Timeline & Actionable Next Steps checklist
- Zero-breakage theme compatibility (dark & light mode)
- Comprehensive empty states and administrative feature-flag guards
"""

from typing import Dict, Any, Tuple, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ui_common import (
    api_request,
    _handle_unauthorized,
    render_svg,
    get_plotly_layout,
    _esc,
    format_error_detail,
)


@st.cache_data(ttl=30)
def _fetch_candidate_dashboard_summary(token: str) -> dict:
    """Fetch cached candidate dashboard summary with 30s TTL."""
    return api_request("GET", "/api/candidate/dashboard-summary", token=token)


def compute_career_readiness_score(data: dict) -> Tuple[int, str]:
    """
    Calculate composite Career Readiness Score:
    0.35 * profile_completeness + 0.30 * ATS + 0.20 * (practice_avg * 10) + 0.15 * mock_avg
    Weights are dynamically renormalized across the components that exist.
    """
    components = []

    # 1. Profile completeness (always present)
    comp_score = data.get("profile_completeness", {}).get("score", 0)
    components.append((0.35, float(comp_score)))

    # 2. ATS Score
    ats_score = data.get("ats", {}).get("latest_score")
    if ats_score is not None and isinstance(ats_score, (int, float)):
        components.append((0.30, float(ats_score)))

    # 3. Practice Avg (scale 1-10 -> 0-100)
    prac_avg = data.get("practice", {}).get("avg_score")
    if prac_avg is not None and isinstance(prac_avg, (int, float)):
        components.append((0.20, float(prac_avg) * 10.0))

    # 4. Mock Avg (scale 0-100)
    mock_avg = data.get("mock_interviews", {}).get("avg_overall")
    if mock_avg is not None and isinstance(mock_avg, (int, float)):
        components.append((0.15, float(mock_avg)))

    total_weight = sum(w for w, _ in components)
    if total_weight <= 0:
        return 0, "Early Stage"

    weighted_sum = sum(w * val for w, val in components)
    final_score = int(round(weighted_sum / total_weight))
    final_score = max(0, min(100, final_score))

    if final_score >= 75:
        verdict = "Interview Ready"
    elif final_score >= 45:
        verdict = "In Development"
    else:
        verdict = "Early Stage"

    return final_score, verdict


def show_candidate_overview_dashboard(token: str, user: dict, profile: dict):
    """
    Render graphical career intelligence overview dashboard for candidate accounts.
    """
    theme = st.session_state.get("theme", "dark")
    is_dark = (theme == "dark")
    text_color = "#F8FAFC" if is_dark else "#0F172A"
    grid_color = "rgba(255,255,255,0.08)" if is_dark else "rgba(15,23,42,0.06)"

    # 1. Fetch data
    with st.spinner("Loading career telemetry & performance metrics..."):
        res = _fetch_candidate_dashboard_summary(token)

    if isinstance(res, dict) and res.get("__unauthorized"):
        _handle_unauthorized(res)
        return

    if isinstance(res, dict) and ("error" in res or "detail" in res):
        st.error(format_error_detail(res.get("error") or res.get("detail")))
        if st.button("Retry Loading Dashboard", key="btn_retry_cand_dash"):
            _fetch_candidate_dashboard_summary.clear()
            st.rerun()
        return

    data = res if isinstance(res, dict) else {}
    flags = data.get("feature_flags", {})

    # 2. Header Strip: Greeting, Readiness Gauge & Refresh
    user_display_name = _esc(user.get("full_name") or profile.get("name") or "Candidate")
    readiness_score, readiness_verdict = compute_career_readiness_score(data)

    head_left, head_right = st.columns([1.6, 1.2])

    with head_left:
        st.markdown(f"""
        <div style='padding-top:12px;'>
            <div style='display:flex;align-items:center;gap:8px;'>
                <span class='sh-badge sh-badge-primary'>CANDIDATE INTELLIGENCE</span>
                <span style='font-size:12px;color:var(--text-subtle);'>Status: <strong>{readiness_verdict}</strong></span>
            </div>
            <h1 class='sh-title' style='margin-top:6px;font-size:26px;'>Welcome back, {user_display_name}!</h1>
            <div class='sh-subtitle'>Track your profile optimization, practice progression, ATS diagnostics, and requisition fit.</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        c_ref, _ = st.columns([1, 2])
        with c_ref:
            if st.button("🔄 Refresh Data", key="cand_dash_refresh_btn", use_container_width=True, type="secondary"):
                _fetch_candidate_dashboard_summary.clear()
                st.rerun()

    with head_right:
        try:
            status_color = "#10B981" if readiness_score >= 70 else ("#F59E0B" if readiness_score >= 40 else "#EF4444")
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=readiness_score,
                number={"suffix": "%", "font": {"size": 28, "color": text_color, "family": "Inter"}},
                title={"text": "Career Readiness Index", "font": {"size": 13, "color": text_color, "family": "Inter"}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": grid_color, "nticks": 5},
                    "bar": {"color": status_color, "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)",
                    "borderwidth": 0,
                    "steps": [
                        {"range": [0, 40], "color": "rgba(239, 68, 68, 0.20)"},
                        {"range": [40, 70], "color": "rgba(245, 158, 11, 0.20)"},
                        {"range": [70, 100], "color": "rgba(16, 185, 129, 0.20)"},
                    ],
                },
            ))
            fig_gauge.update_layout(
                **get_plotly_layout(theme),
                height=180,
                margin=dict(l=20, r=20, t=30, b=10),
            )
            st.plotly_chart(fig_gauge, use_container_width=True)
        except Exception as e:
            st.warning(f"Could not render readiness gauge: {e}")

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    # 3. KPI Metrics Row (5 Cards)
    p_comp = data.get("profile_completeness", {}).get("score", 0)
    ats_sc = data.get("ats", {}).get("latest_score")
    ats_val_str = f"{ats_sc}%" if ats_sc is not None else "—"
    prac_avg = data.get("practice", {}).get("avg_score")
    prac_val_str = f"{prac_avg}/10" if prac_avg is not None else "—"
    mock_done = data.get("mock_interviews", {}).get("completed", 0)
    skills_tot = data.get("skills", {}).get("total", 0)

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.markdown(f"""
        <div class='sh-stat-card'>
            <div class='sh-stat-label'>Profile Completeness</div>
            <div class='sh-stat-value' style='color:#6366F1;'>{p_comp}%</div>
        </div>
        """, unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class='sh-stat-card'>
            <div class='sh-stat-label'>ATS Resume Score</div>
            <div class='sh-stat-value' style='color:#10B981;'>{ats_val_str}</div>
        </div>
        """, unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class='sh-stat-card'>
            <div class='sh-stat-label'>Practice Average</div>
            <div class='sh-stat-value' style='color:#3B82F6;'>{prac_val_str}</div>
        </div>
        """, unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
        <div class='sh-stat-card'>
            <div class='sh-stat-label'>Mock Interviews</div>
            <div class='sh-stat-value' style='color:#EC4899;'>{mock_done}</div>
        </div>
        """, unsafe_allow_html=True)
    with k5:
        st.markdown(f"""
        <div class='sh-stat-card'>
            <div class='sh-stat-label'>Skills Identified</div>
            <div class='sh-stat-value' style='color:#F59E0B;'>{skills_tot}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # 4. Row 1 Charts: Profile Completeness Breakdown & Mock Competency Radar
    r1_left, r1_right = st.columns(2)

    with r1_left:
        st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Portfolio Completeness Audit</h3>", unsafe_allow_html=True)
        try:
            b_data = data.get("profile_completeness", {}).get("breakdown", {})
            labels = ["Resume", "Skills", "Experience", "Education", "Projects", "Certifications", "Contact"]
            keys = ["resume_uploaded", "skills", "experience", "education", "projects", "certifications", "contact"]
            vals = [b_data.get(k, 0) for k in keys]
            bar_colors = ["#10B981" if v >= 100 else "#F59E0B" for v in vals]

            fig_comp = go.Figure(go.Bar(
                x=vals,
                y=labels,
                orientation='h',
                marker=dict(color=bar_colors),
                text=[f"{v}%" for v in vals],
                textposition="auto",
            ))
            fig_comp.update_layout(
                **get_plotly_layout(theme),
                xaxis=dict(range=[0, 120], showgrid=False, title="Completion Status"),
                height=260,
                margin=dict(l=20, r=20, t=15, b=20),
            )
            st.plotly_chart(fig_comp, use_container_width=True)

            missing_sections = data.get("profile_completeness", {}).get("missing", [])
            if missing_sections:
                badges = " ".join([f"<span class='sh-badge sh-badge-warning'>⚠️ {_esc(m)} Missing</span>" for m in missing_sections])
                st.markdown(f"<div style='margin-top:6px;font-size:12px;'><strong>Suggested Additions:</strong> {badges}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='margin-top:6px;font-size:12px;color:var(--success-text);'>✓ All portfolio dimensions fully populated.</div>", unsafe_allow_html=True)
        except Exception as e:
            st.warning(f"Could not render profile completeness breakdown: {e}")

    with r1_right:
        st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Interview Competency Radar</h3>", unsafe_allow_html=True)
        if not flags.get("mock_interview", True):
            st.markdown("""
            <div class='sh-card-sm' style='opacity:0.7;border-style:dashed;margin-top:10px;'>
                <div style='font-size:13px;font-weight:600;color:var(--text-subtle);'>⚠️ Mock Interview Feature Disabled</div>
                <div style='font-size:11px;color:var(--text-subtle);margin-top:4px;'>This module is currently disabled by a platform administrator.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            try:
                latest_comps = data.get("mock_interviews", {}).get("latest_competencies")
                if latest_comps and isinstance(latest_comps, dict) and len(latest_comps) >= 3:
                    categories = list(latest_comps.keys())
                    c_values = list(latest_comps.values())
                    cat_closed = categories + [categories[0]]
                    val_closed = c_values + [c_values[0]]

                    fig_radar = go.Figure(data=go.Scatterpolar(
                        r=val_closed,
                        theta=cat_closed,
                        fill='toself',
                        fillcolor='rgba(99, 102, 241, 0.20)' if is_dark else 'rgba(37, 99, 235, 0.20)',
                        line=dict(color='#6366F1' if is_dark else '#2563EB', width=2),
                    ))
                    fig_radar.update_layout(
                        **get_plotly_layout(theme),
                        polar=dict(
                            radialaxis=dict(visible=True, range=[0, 100], gridcolor=grid_color),
                            angularaxis=dict(gridcolor=grid_color),
                        ),
                        showlegend=False,
                        height=280,
                        margin=dict(l=30, r=30, t=20, b=20),
                    )
                    st.plotly_chart(fig_radar, use_container_width=True)
                else:
                    st.markdown("""
                    <div class='sh-card-sm' style='text-align:center;padding:26px 16px;margin-top:8px;'>
                        <div style='font-size:24px;margin-bottom:6px;'>🎯</div>
                        <div style='font-size:14px;font-weight:600;color:var(--text-primary);'>No Competency Radar Available</div>
                        <div style='font-size:12px;color:var(--text-subtle);margin-top:4px;margin-bottom:14px;'>Complete your first interactive mock interview to evaluate core competency dimensions.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("🚀 Start AI Mock Interview", key="cand_dash_nav_mock", use_container_width=True, type="primary"):
                        st.session_state["candidate_nav_radio"] = "AI Mock Interview"
                        st.rerun()
            except Exception as e:
                st.warning(f"Could not render competency radar: {e}")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # 5. Row 2 Charts: Practice Score Progression & ATS Trajectory
    r2_left, r2_right = st.columns(2)

    with r2_left:
        st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Practice Score Progression</h3>", unsafe_allow_html=True)
        if not flags.get("practice", True):
            st.markdown("""
            <div class='sh-card-sm' style='opacity:0.7;border-style:dashed;margin-top:10px;'>
                <div style='font-size:13px;font-weight:600;color:var(--text-subtle);'>⚠️ Practice Assessment Disabled</div>
                <div style='font-size:11px;color:var(--text-subtle);margin-top:4px;'>Practice question evaluations are disabled by platform policy.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            try:
                trend_data = data.get("practice", {}).get("trend", [])
                by_type = data.get("practice", {}).get("by_type", {})
                if trend_data:
                    x_indices = [f"#{i+1}" for i in range(len(trend_data))]
                    y_scores = [item.get("score", 0.0) for item in trend_data]
                    fig_trend = go.Figure()
                    fig_trend.add_trace(go.Scatter(
                        x=x_indices,
                        y=y_scores,
                        mode="lines+markers",
                        line=dict(color="#3B82F6", width=2.5),
                        marker=dict(size=7, color="#10B981"),
                        name="Score (1-10)",
                    ))
                    fig_trend.update_layout(
                        **get_plotly_layout(theme),
                        yaxis=dict(title="Score (1-10)", range=[0, 10.5]),
                        xaxis=dict(title="Attempts (Chronological)"),
                        height=240,
                        margin=dict(l=25, r=20, t=15, b=20),
                    )
                    st.plotly_chart(fig_trend, use_container_width=True)

                    if by_type:
                        b_types = list(by_type.keys())
                        b_vals = [f"<strong>{k}</strong>: {v}/10" for k, v in by_type.items()]
                        st.markdown(f"<div style='font-size:12px;color:var(--text-secondary);'>{' &nbsp;|&nbsp; '.join(b_vals)}</div>", unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div class='sh-card-sm' style='text-align:center;padding:26px 16px;margin-top:8px;'>
                        <div style='font-size:24px;margin-bottom:6px;'>📝</div>
                        <div style='font-size:14px;font-weight:600;color:var(--text-primary);'>No Practice Attempts Recorded</div>
                        <div style='font-size:12px;color:var(--text-subtle);margin-top:4px;margin-bottom:14px;'>Solve technical, behavioral, or scenario-based practice questions to track performance.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("✍️ Try Practice Questions", key="cand_dash_nav_practice", use_container_width=True, type="primary"):
                        st.session_state["candidate_nav_radio"] = "Demo Practice Questions"
                        st.rerun()
            except Exception as e:
                st.warning(f"Could not render practice trend chart: {e}")

    with r2_right:
        st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>ATS Resume Score History</h3>", unsafe_allow_html=True)
        if not flags.get("resume_ai", True):
            st.markdown("""
            <div class='sh-card-sm' style='opacity:0.7;border-style:dashed;margin-top:10px;'>
                <div style='font-size:13px;font-weight:600;color:var(--text-subtle);'>⚠️ Resume Intelligence Disabled</div>
                <div style='font-size:11px;color:var(--text-subtle);margin-top:4px;'>AI resume screening is disabled by an administrator.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            try:
                ats_hist = data.get("ats", {}).get("history", [])
                if ats_hist:
                    # Chronological order
                    ats_chron = list(reversed(ats_hist))
                    dates = [item.get("date") or f"Run #{i+1}" for i, item in enumerate(ats_chron)]
                    scores = [item.get("score", 0) for item in ats_chron]
                    fig_ats = go.Figure()
                    fig_ats.add_trace(go.Scatter(
                        x=dates,
                        y=scores,
                        mode="lines+markers",
                        fill="tozeroy",
                        fillcolor="rgba(16, 185, 129, 0.15)",
                        line=dict(color="#10B981", width=2.5),
                        marker=dict(size=7),
                        name="ATS Score",
                    ))
                    fig_ats.update_layout(
                        **get_plotly_layout(theme),
                        yaxis=dict(title="Score (0-100)", range=[0, 105]),
                        xaxis=dict(title="Audit Date"),
                        height=240,
                        margin=dict(l=25, r=20, t=15, b=20),
                    )
                    st.plotly_chart(fig_ats, use_container_width=True)

                    strengths = data.get("ats", {}).get("strengths", [])
                    if strengths:
                        str_tags = " ".join([f"<span class='sh-badge sh-badge-success'>✓ {_esc(s)}</span>" for s in strengths[:3]])
                        st.markdown(f"<div style='font-size:12px;margin-top:4px;'><strong>Identified Strengths:</strong> {str_tags}</div>", unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div class='sh-card-sm' style='text-align:center;padding:26px 16px;margin-top:8px;'>
                        <div style='font-size:24px;margin-bottom:6px;'>📄</div>
                        <div style='font-size:14px;font-weight:600;color:var(--text-primary);'>No ATS Analysis Run Yet</div>
                        <div style='font-size:12px;color:var(--text-subtle);margin-top:4px;margin-bottom:14px;'>Upload your resume document to run an automated 10-dimension ATS compatibility audit.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("📤 Upload Resume for ATS Audit", key="cand_dash_nav_ats", use_container_width=True, type="primary"):
                        st.session_state["candidate_nav_radio"] = "Resume Intelligence & ATS"
                        st.rerun()
            except Exception as e:
                st.warning(f"Could not render ATS history chart: {e}")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # 6. Row 3: Best Job Fits (Open Positions)
    st.markdown("<h3 style='font-size:16px;margin-bottom:8px;'>Target Requisition Match Alignment</h3>", unsafe_allow_html=True)
    st.caption("Semantic candidate-job match compatibility across active requisitions.")

    try:
        job_fits = data.get("job_fit", [])
        if job_fits:
            df_fit = pd.DataFrame(job_fits)
            fig_fit = px.bar(
                df_fit,
                x="fit_percent",
                y="title",
                orientation="h",
                color="fit_percent",
                color_continuous_scale="Purples" if is_dark else "Blues",
                labels={"fit_percent": "Match Compatibility %", "title": "Role Requisition"},
            )
            fig_fit.update_layout(
                **get_plotly_layout(theme),
                height=min(300, 45 * len(job_fits) + 70),
                margin=dict(l=20, r=20, t=15, b=20),
                xaxis=dict(range=[0, 105]),
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig_fit, use_container_width=True)

            # Expandable skills inspection per job
            fit_cols = st.columns(min(len(job_fits), 3))
            for idx, jf in enumerate(job_fits[:3]):
                col_target = fit_cols[idx]
                with col_target:
                    with st.expander(f"**{jf['title']}** ({jf['fit_percent']}%)", expanded=False):
                        st.caption(f"Department: {jf['department']}")
                        matched_tags = " ".join([f"<span class='sh-badge sh-badge-success'>✓ {_esc(s)}</span>" for s in jf.get("matched", [])]) or "<span style='font-size:11px;color:var(--text-subtle);'>None</span>"
                        missing_tags = " ".join([f"<span class='sh-badge sh-badge-danger'>✗ {_esc(s)}</span>" for s in jf.get("missing", [])]) or "<span style='font-size:11px;color:var(--text-subtle);'>All requirements met</span>"
                        st.markdown(f"""
                        <div style='font-size:11px;font-weight:600;margin-top:4px;'>MATCHED SKILLS:</div>
                        <div style='margin-bottom:8px;'>{matched_tags}</div>
                        <div style='font-size:11px;font-weight:600;'>SKILL GAPS:</div>
                        <div>{missing_tags}</div>
                        """, unsafe_allow_html=True)
        else:
            st.info("No active open job requisitions available for semantic match alignment.")
    except Exception as e:
        st.warning(f"Could not render job fit alignment: {e}")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # 7. Row 4: Recent Activity & Recommended Next Steps
    act_col, steps_col = st.columns([1.2, 1])

    with act_col:
        st.markdown("<h3 style='font-size:16px;margin-bottom:12px;'>Recent Candidate Activity</h3>", unsafe_allow_html=True)
        activity_items = data.get("activity", [])
        if activity_items:
            for act in activity_items[:6]:
                a_type = act.get("type")
                icon_name = "target" if a_type == "practice" else ("chat" if a_type == "mock" else ("award" if a_type == "ats" else "users"))
                icon_color = "#3B82F6" if a_type == "practice" else ("#10B981" if a_type == "mock" else ("#F59E0B" if a_type == "ats" else "#6366F1"))
                st.markdown(f"""
                <div class='sh-card-sm' style='display:flex;align-items:center;gap:12px;margin-bottom:8px;padding:10px 14px;'>
                    <div>{render_svg(icon_name, 16, icon_color)}</div>
                    <div style='flex:1;'>
                        <div style='font-size:13px;font-weight:600;color:var(--text-primary);'>{_esc(act.get('label'))}</div>
                        <div style='font-size:11px;color:var(--text-subtle);'>{_esc(act.get('date'))}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class='sh-card-sm' style='padding:16px;color:var(--text-subtle);font-size:13px;'>
                No recent activity logged. Complete an interview practice question or upload your resume to generate timeline entries.
            </div>
            """, unsafe_allow_html=True)

    with steps_col:
        st.markdown("<h3 style='font-size:16px;margin-bottom:12px;'>Recommended Next Steps</h3>", unsafe_allow_html=True)
        next_steps = data.get("next_steps", [])
        if next_steps:
            for idx, step in enumerate(next_steps, 1):
                st.markdown(f"""
                <div class='sh-card-sm' style='margin-bottom:8px;padding:10px 14px;border-left:3px solid var(--primary);'>
                    <div style='font-size:11px;font-weight:700;color:var(--primary);text-transform:uppercase;'>ACTION {idx}</div>
                    <div style='font-size:13px;font-weight:500;color:var(--text-primary);margin-top:2px;'>{_esc(step)}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class='sh-card-sm' style='padding:16px;color:var(--success-text);font-size:13px;'>
                ✓ All immediate portfolio checklist items are complete. Keep honing your practice interview scores!
            </div>
            """, unsafe_allow_html=True)
