# CHANGELOG: Stabilization, Security & Glitch Fixes

This document records all bugs, crashes, security vulnerabilities, and inconsistencies identified and resolved during the system stabilization pass across all three platform roles (`Candidate`, `Recruiter`, `Admin`) on branch `fix/stabilization`.

---

## High Severity Fixes

### [H1] Bcrypt 72-Byte Password Overflow Crash
- **Symptom**: Supplying a password longer than 72 bytes caused bcrypt to crash with an unhandled `ValueError: password cannot be longer than 72 bytes`, returning an HTTP 500 error instead of a clean validation error.
- **Root Cause**: Bcrypt has an architectural 72-byte truncation limit. Unvalidated user inputs longer than 72 UTF-8 bytes triggered an internal assertion.
- **Fix**:
  - In `auth.py:hash_password`, validate `len(password.encode("utf-8")) <= 72` before calling `pwd_context.hash()`.
  - In `schemas.py:UserRegisterRequest` and `schemas.py:AdminCreateUserRequest`, added `@field_validator('password')` enforcing maximum 72 bytes.
  - In `app.py:show_register`, added client-side pre-validation for byte length.
- **Regression Tests**: `tests/test_phase1_fixes.py::test_password_length_validation_rejects_over_72_bytes`, `test_hash_password_guards_against_over_72_bytes`.

### [H2] Dataset Candidate Collapse in Recruiter Directory
- **Symptom**: In datasets where candidate records have empty or missing names and emails (e.g. raw Kaggle resume imports), the candidate pool collapsed from ~9,543 candidates down to just 1 visible candidate.
- **Root Cause**: In `app.py:get_cached_candidates`, the deduplication logic evaluated identity key `(str(c.get("name")).strip().lower(), str(c.get("email")).strip().lower())`. `str(None)` evaluated to `"none"`, which was truthy. Every nameless candidate evaluated to `("none", "none")` and was discarded after the first one.
- **Fix**: Check `name` and `email` against empty and sentinel values (`"none"`, `"null"`, `"nan"`, `""`). If both are missing, deduplicate by candidate primary key `candidate_id` (or Python object ID) instead of the compound name-email tuple.
- **Regression Tests**: `tests/test_phase3_fixes.py::test_h2_deduplication_preserves_nameless_dataset_candidates`.

### [H3] Missing Application Match Score on Pipeline Insertion
- **Symptom**: When candidates were added to the recruitment pipeline or ingested, `Application.match_score` remained `NULL`, causing 0% match scores or sorting anomalies.
- **Root Cause**: Pipeline assignment route `/api/pipeline` only saved `stage` and `notes` without computing the matching engine score between candidate skills and job requirements.
- **Fix**: In `api.py:add_to_pipeline` and `update_pipeline_stage`, invoke `_pipeline_match_score(cand, job)` to compute and persist the multi-factor fit score into `Application.match_score`.
- **Regression Tests**: `tests/test_phase2_fixes.py::test_h3_pipeline_match_score_calculation`.

### [H4] Database Lock Concurrency Bottleneck
- **Symptom**: Under simultaneous API requests or during bulk resume parsing, SQLite threw `sqlite3.OperationalError: database is locked`.
- **Root Cause**: SQLite defaulted to rollback journal mode without write-ahead logging (WAL) or busy timeouts.
- **Fix**: In `database.py`, configured SQLite connection pragma events: `PRAGMA journal_mode=WAL;`, `PRAGMA busy_timeout=30000;`, and `PRAGMA synchronous=NORMAL;`.
- **Regression Tests**: `tests/test_phase1_fixes.py::test_sqlite_wal_and_busy_timeout_configured`.

### [H5] Kanban Column Styling & Layout Break
- **Symptom**: The recruitment pipeline Kanban board columns collapsed or wrapped inconsistently across Streamlit versions.
- **Root Cause**: Streamlit updated its column container test ID from `div[data-testid="column"]` to `div[data-testid="stColumn"]`. Existing CSS rules only matched the legacy attribute.
- **Fix**: Updated Kanban CSS selectors in `app.py` to match both `div[data-testid="column"]` and `div[data-testid="stColumn"]`.

### [H6] Data Health Check False Positives on System Markers
- **Symptom**: The Admin Data Health monitor flagged `.gitkeep` and synthetic dataset markers in `uploads/` as unreferenced orphaned files.
- **Root Cause**: The directory scanner in `admin_routes.py:get_data_health` included hidden dotfiles (`.gitkeep`, `.DS_Store`) and dataset marker files.
- **Fix**: Filtered out files starting with `.` or matching dataset marker prefixes from orphan file tracking.
- **Regression Tests**: `tests/test_phase2_fixes.py::test_h6_data_health_skips_dataset_markers_and_dotfiles`.

### [H7] UI Freezes on Large Pools (Candidate Directory & Matcher)
- **Symptom**: Loading the Candidate Directory or Job Matcher with large datasets (>5,000 candidates) locked up the browser thread due to rendering thousands of DOM cards simultaneously.
- **Root Cause**: Lack of pagination and display caps on heavy HTML cards.
- **Fix**:
  - Implemented 25-item pagination with page controls in `app.py:show_candidates_view` while preserving full dataset export.
  - Capped Kanban column cards to 25 items with a "Show more" expander.
  - Capped Job Matcher results to top 50 candidates by default with an optional "Show all" toggle.

### [H8] Admin UI Duplicate Widget Key Collisions
- **Symptom**: Streamlit threw `DuplicateWidgetID` errors when multiple users had action panels opened simultaneously.
- **Root Cause**: Widget keys in `admin_dashboard.py` used static strings like `"role_sel"` or `"active_chk"`.
- **Fix**: Suffix all interactive widget keys in user rows with `_{target_id}`.

### [H9] Audit Log Pollution from Auto-Fetched Downloads
- **Symptom**: Accessing the Admin System Backup or Audit Log pages immediately created spurious audit log rows without the admin performing an export.
- **Root Cause**: Streamlit download buttons executed HTTP requests to `/api/admin/backup` on every initial page render to populate button binary buffers.
- **Fix**: Replaced auto-fetch download buttons with a two-step on-demand pattern ("Prepare Backup" / "Prepare Export") utilizing session state.

### [H10] Public Registration Bypass When Registration Closed
- **Symptom**: Setting `registration_open=false` in Platform Settings did not block public self-registration.
- **Root Cause**: `/api/auth/register` did not check the `registration_open` platform setting.
- **Fix**: In `api.py:register`, query `settings_store.get_setting(db, "registration_open", "true")`. If `"false"`, return HTTP 403 Forbidden. Added UI notice and disabled buttons in `app.py`.
- **Regression Tests**: `tests/test_phase2_fixes.py::test_h10_registration_closed_returns_403`.

### [H11] Soft-Delete Leakage in Candidate Listings & Purges
- **Symptom**: Soft-deleted candidates (with `deleted_at IS NOT NULL`) remained visible in certain queries and were counted in health checks.
- **Root Cause**: Inconsistent filtering of `Candidate.deleted_at.is_(None)` across endpoints.
- **Fix**: Filter `deleted_at.is_(None)` across all candidate listing, analytics, matching, and purge routes. Added `POST /api/admin/candidates/{id}/restore` to un-delete.
- **Regression Tests**: `tests/test_phase2_fixes.py::test_h11_soft_delete_and_restoration`.

### [H12] Bulk Ingest Memory Footprint
- **Symptom**: `data_ingest.py` consumed excessive memory when processing thousands of resumes.
- **Root Cause**: Batch transactions and objects were held in SQLAlchemy session memory without clearing.
- **Fix**: Added explicit `db.flush()`, `db.commit()`, and `db.expunge_all()` every 200 records.

### [H13] Multi-Worker Table Creation Startup Race Condition
- **Symptom**: Running multiple Uvicorn workers caused intermittent `sqlite3.OperationalError: table users already exists`.
- **Root Cause**: Concurrently executing `Base.metadata.create_all()` without database locking.
- **Fix**: Wrapped initial table creation and migration in a file lock in `database.py`.

---

## Medium Severity Fixes

### [M1] Recruiter Dashboard Metric Accuracy
- **Symptom**: Active jobs metric counted closed jobs, and recruitment funnel percentages were hardcoded (72%, 38%, 16%, 5%).
- **Root Cause**: Direct `len(jobs_list)` without status filtering; static HTML mockup values.
- **Fix**: In `app.py:show_dashboard_overview`, filter `status.strip().lower() == "open"` and compute live funnel counts from `get_cached_pipeline()["counts"]`.
- **Regression Tests**: `tests/test_phase3_fixes.py::test_m1_active_jobs_count_filters_status`.

### [M2] Recruiter Activity Upload Metric
- **Symptom**: Recruiter activity monitor in Admin dashboard showed 0 uploads for recruiters who had uploaded candidates.
- **Root Cause**: Query counted resume parsing sessions instead of `Candidate` records where `created_by == user_id`.
- **Fix**: Updated `admin_routes.py:get_recruiter_activity` to count both assigned jobs and created candidate profiles.
- **Regression Tests**: `tests/test_phase2_fixes.py::test_m2_recruiter_activity_counts_uploads`.

### [M4] XSS and HTML Escaping in Raw Markdown
- **Symptom**: Candidate names, email addresses, job titles, or maintenance notices containing special characters (`<`, `>`, `&`) broke layout or risked script injection.
- **Root Cause**: String interpolation directly inside `st.markdown(..., unsafe_allow_html=True)` without HTML escaping.
- **Fix**: Introduced `_esc()` helper in `ui_common.py` and wrapped all dynamic user strings before interpolation.
- **Regression Tests**: `tests/test_phase3_fixes.py::test_ui_common_esc_helper`.

### [M5] Raw JSON Display in Candidate Profile Drawer
- **Symptom**: Candidate education, experience, and project histories rendered as raw unformatted JSON strings `[{'degree': ...}]`.
- **Root Cause**: Missing parser/formatter helper before card rendering.
- **Fix**: Added `_format_item_readable()` in `app.py` to parse structured JSON dictionaries and render formatted badges and bullets.

### [M6] Unclosed Drawer Container DOM Bug
- **Symptom**: The candidate profile drawer caused lower page elements to indent improperly.
- **Root Cause**: An unclosed `<div class='sh-drawer-body'>` in the raw HTML markdown block.
- **Fix**: Replaced raw HTML wrapper with native `with st.container(border=True):`.

### [M7] Kanban Stage Selectbox State Stale After Move
- **Symptom**: After moving a candidate to a new stage in Kanban, the stage selectbox remained on the previous selection.
- **Root Cause**: Streamlit retained the old selectbox widget key in `st.session_state`.
- **Fix**: Delete `st.session_state[f"pipe_move_{app_id}"]` after successful stage mutation.

### [M8] AI Interview & Mock Interview Error Handling
- **Symptom**: When AI question generation or session initialization failed, the UI remained blank without feedback.
- **Root Cause**: Missing error checks and failure alerts on API responses.
- **Fix**: Added explicit error inspection and `st.error(format_error_detail(...))` notifications. Disabled mock interview launch when no open jobs exist.

### [M10] FastAPI Connection Pooling
- **Symptom**: Database session exhaustion under sustained load.
- **Root Cause**: SQLAlchemy `NullPool` recreated connections on every thread without reuse.
- **Fix**: Configured `QueuePool` with reasonable pool size and overflow parameters for SQLite WAL concurrency in `database.py`.

### [M11] Startup Orchestrator Graceful Shutdown
- **Symptom**: Terminating `run.py` occasionally left orphaned Uvicorn or Streamlit processes holding ports 8000/8501.
- **Root Cause**: Unhandled `SIGINT` / `SIGTERM` signals.
- **Fix**: In `run.py`, attached signal handlers and `atexit` hooks to terminate child processes gracefully.

### [M12] Inactive Admin Job Reassignment
- **Symptom**: Reassigning a job to a deactivated user succeeded, leaving the job in an unmanaged state.
- **Root Cause**: `admin_routes.py:reassign_job` did not check `target_user.is_active`.
- **Fix**: Added validation requiring `target_user.is_active == True`.

### [M13] Session Sign-Out Visual Theme Preservation
- **Symptom**: Clicking Sign Out reset the user's selected Light/Dark mode back to default Dark mode.
- **Root Cause**: `st.session_state.clear()` deleted the `"theme"` key.
- **Fix**: Implemented `_clear_auth_session()` in `app.py` and `admin_dashboard.py` which preserves `st.session_state["theme"]`.

### [M14] Audio TTS / STT Redundant Execution
- **Symptom**: Streamlit reruns repeatedly converted the same text to speech or transcribed identical audio.
- **Root Cause**: Absence of audio caching and concurrency protection around the `pyttsx3` COM engine.
- **Fix**: Added `_TTS_LOCK` threading mutex and an in-memory STT cache keyed by SHA-256 audio bytes hash.

### [M15] Pipeline Upload Feedback
- **Symptom**: Uploading a resume in the Recruitment Pipeline view lacked clear visual feedback on which stage the candidate was placed into.
- **Root Cause**: Default stage assignment without confirmation messaging.
- **Fix**: Added explicit informational notice and automatic fallback to `"applied"` stage when no job requisition was selected.

### [M16] Acronym Casing in Analytics & Skill Badges
- **Symptom**: Technology acronyms like `AWS`, `SQL`, `NLP`, `CI/CD`, `GCP` rendered in title case (`Aws`, `Sql`, `Nlp`, `Ci/Cd`).
- **Root Cause**: Direct `.title()` calls applied to all tokens.
- **Fix**: Created `SKILL_DISPLAY_MAP` and `format_skill_display()` in `skill_taxonomy.py` to preserve proper industry casing.
- **Regression Tests**: `tests/test_phase3_fixes.py::test_m16_skill_display_map_preserves_acronym_casing`.

### [M17] Audit Log Query Timestamp Alignment
- **Symptom**: Filtering audit logs by date range failed to match logs from the start or end dates.
- **Root Cause**: Comparison between naive datetime and timezone-aware UTC timestamps.
- **Fix**: Normalized date boundaries to UTC in `admin_routes.py:get_audit_logs`.

---

## Architectural Decisions & Trade-Offs

1. **Role Governance**: Public self-registration is strictly restricted to the `Candidate` role (`SUPPORTED_ROLES = ["Candidate", "Recruiter", "Admin"]`). `Recruiter` and `Admin` accounts must be provisioned by a platform Administrator via `/api/admin/users`.
2. **Soft Deletion Policy**: Candidates are soft-deleted by setting `Candidate.deleted_at = datetime.now(timezone.utc)`. All standard candidate listing, matching, pipeline, and analytics routes exclude soft-deleted rows. Soft-deleted candidates can be permanently inspected, restored, or purged only by an Administrator in Data Governance.
3. **Audit Log Non-Disruption**: `services/audit.py:log_event` is guaranteed never to raise exceptions or break caller workflows. If database insertion fails, it rolls back and logs locally to prevent user-facing transaction aborts.
4. **AI Telemetry Safety**: `services/llm_client.py:call_llm` records token and latency metrics in `LlmUsage` inside a safe `finally:` block that suppresses recording errors if the database session is interrupted.
