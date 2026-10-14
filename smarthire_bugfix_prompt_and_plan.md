# SmartHire AI: Bug-Fix Prompt and Implementation Plan
Target executors: **Gemini 3.8 Anti Gravity** (lead: audit, multi-file fixes, verification) and **Gemini 3.8 Flash** (fast mechanical edits, tests, docs).

Hard rule for both agents: **fix bugs and glitches only. Do not redesign, rename routes, change features, remove features, change the DB schema, or alter the UI layout/theme.** After the fixes, the app must run end to end exactly as designed.

> Scope note: this audit was done from the files provided (`api.py`, `admin_routes.py`, `admin_dashboard.py`, `app.py`, `ui_common.py`, `database.py`, `models.py`, `schemas.py`, `auth.py`, `parser.py`, `file_loader.py`, `data_ingest.py`, `run.py`, `requirements.txt`, `README.md`, `.env`, `.gitignore`). **Not provided and therefore not audited:** `services/*` (audit, candidate_service, hiring_score, interview_assistant, llm_client, matching_engine, settings_store, skill_gap_analysis), `tests/*`, `docs/permission_matrix.md`, `.env.example`, `data/`. Phase 0 and Phase 4 make the agents audit those first-hand.

---

## 0. Security action before anything else
The `.env` that was shared contains a live-looking Sarvam API key and the JWT secret. Treat both as exposed: **rotate the Sarvam key and the `SMARTHIRE_SECRET_KEY`**, and never paste `.env` contents into prompts, logs, commits or tests. `.env` is already gitignored; keep it that way. (The key is intentionally not reproduced in this document.)

---

## 1. MASTER PROMPT (paste into Anti Gravity as the first message)

```
You are the lead engineer fixing bugs and glitches in "SmartHire AI", a FastAPI (port 8000) + Streamlit (port 8501) + SQLite recruitment platform with three roles: Candidate, Recruiter, Admin.

OBJECTIVE
Find and fix every bug, crash, glitch and inconsistency so the project runs cleanly end to end for all three roles. Do NOT change features, architecture, API routes/contracts, DB schema, visual design, or behavior that is already correct. Minimal, surgical diffs only.

RULES
1. Work on a new git branch `fix/stabilization`. Commit per phase with clear messages.
2. Before editing, read the whole repo, including files I did not summarize: services/*.py, tests/*.py, docs/permission_matrix.md, .env.example, requirements.txt. Never print or commit secrets from .env.
3. Run `pip install -r requirements.txt` in a fresh venv, then `pytest tests/ -v` and record the baseline (README claims 126 passing). Never leave a test that passed before in a failing state. If a test encodes buggy behavior, fix the test and say why in the commit message.
4. For every bug in the register below: reproduce it first (script, curl, or pytest), apply the smallest fix, add a regression test under tests/, and re-run the full suite.
5. The bug register is a starting point, not a ceiling. After finishing it, do a second pass over services/*, every `except Exception: pass`, every unguarded `.first()`, every place `None` can reach `.lower()/.strip()/json.loads`, every Streamlit widget key, and every unescaped f-string inside `st.markdown(..., unsafe_allow_html=True)`. Fix anything else you find and append it to a CHANGELOG_FIXES.md.
6. Where a fix would require a product decision (listed under "Decisions needed"), do NOT decide silently: apply the safest non-breaking option, and list the question in CHANGELOG_FIXES.md.
7. Finish by running the full smoke test in section 6 of the plan, and report: bugs fixed (ID list), tests added, tests still failing (if any), and anything unverifiable.

Use Gemini 3.8 Flash sub-tasks for mechanical work (bulk edits, escaping, width="stretch" migration, writing regression tests, README/requirements edits). Keep root-cause analysis, cross-file fixes and final verification in Anti Gravity.
```

---

## 2. BUG REGISTER

### A. Blockers / High severity

**H1. Bootstrap admin is never created from `.env` (`database.py`)**
- Symptom: fresh install has no Admin, public registration blocks Recruiter/Admin, so nobody can ever provision accounts.
- Cause: `init_db()` reads `BOOTSTRAP_ADMIN_EMAIL/PASSWORD` from `os.environ` *before* `env_loader` has run (`api.py` calls `init_db()` before `auth` is imported). `.env` also has no BOOTSTRAP vars.
- Fix: `import env_loader` at top of `database.py` (before reads). Add `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` placeholders to `.env.example`. Log a clear warning (not the password) when no admin exists and no bootstrap vars are set. Replace the blanket `except Exception: pass` with logging so migration failures are visible.

**H2. Seeded candidates collapse into one in the UI (`app.py: get_cached_candidates`)**
- Cause: dedup uses `str(c.get("name",""))`. For dataset candidates `name`/`email` are `None`, so `str(None)` = `"none"`; every seeded row shares identity `("none","none")` and 9,543 of 9,544 are dropped.
- Fix: treat `None`/`""`/`"none"`/`"null"`/`"nan"` as empty; only dedup by `(name,email)` when both are real values; otherwise dedup by `candidate_id` only.

**H3. Pipeline match score is always empty/zero (`api.py`, 5 call sites)**
- Cause: `matching_engine.score_candidate(cand_dict, job_dict)` is called positionally, but `/hiring-scores` calls it with keywords `candidate_skills=, candidate_experience=, job=`; and the code reads `overall_score`, whereas the engine/schema key is `final_score`. The `except Exception: match_score=None` hides it.
- Sites: `get_recruitment_pipeline`, `update_application_stage`, `add_application_to_pipeline`, `create_candidate_and_pipeline`, `get_pipeline_application_detail`.
- Fix: one helper `_pipeline_match_score(cand_row, job_row)` that calls the engine with the real signature (verify in `services/matching_engine.py`), reads `final_score`, and is reused at all 5 sites. Log (don't swallow) failures.

**H4. `run.py` can freeze the backend and only works on Windows**
- Cause: child processes use `stdout=PIPE` that is never read, so after ~64 KB of uvicorn/Streamlit logs the child blocks. Paths are hard-coded to `venv/Scripts/python.exe` and `streamlit.exe`.
- Fix: use `sys.executable` and `[sys.executable, "-m", "streamlit", "run", "app.py", ...]`; let child output inherit the terminal (or write to log files); on startup failure read output safely. Update the banner (it still says "Milestone 1").

**H5. Streamlit version compatibility (verify first, then fix)**
- `requirements.txt` has `streamlit>=1.60.0`. The code uses `use_container_width=True` on `st.button`, `st.dataframe`, `st.plotly_chart` (deprecated in favor of `width="stretch"`; may raise or warn on current versions) and CSS selectors `div[data-testid="column"]` (newer builds expose `stColumn`), which would silently disable the Kanban grid styling.
- Fix: install the resolved version, run the app, and check for deprecation errors. Migrate to `width="stretch"` where required; make selectors match both `[data-testid="column"], [data-testid="stColumn"]`. **Pin Streamlit to the exact tested version.**

**H6. Resume file bookkeeping is wrong, producing false "missing/orphan" reports**
- Candidate-portal upload saves `uploads/user_{id}_{filename}` but stores `resume_path = filename`, so Data Governance reports it Missing and the real file Orphan.
- Recruiter upload saves `safe_filename` but stores raw `file.filename` (unsanitized, may contain path parts).
- Seeded `dataset_row_N` paths all appear as Missing (about 9.5k false positives); `.gitkeep` shows as an orphan.
- Fix: store the actual saved basename in `resume_path` at both upload sites (and use it in the lookup `Candidate.resume_path == ...`); in `admin_routes.get_data_health` skip `dataset_row_*` paths and dotfiles.

**H7. UI renders thousands of widgets (Candidates, Job Matcher, Pipeline)**
- With 9.5k candidates, `show_candidates_view` renders every filtered card with its own button; the matcher renders every ranked candidate; the pipeline returns/renders every application per column. The page hangs.
- Fix (behavior-preserving): paginate Candidates (25/50 per page with page controls, export still covers the full filtered set); cap matcher display to top N (e.g., 50) with a "show more"; cap each Kanban column (e.g., 25 cards + "Show more", counts still show true totals). Keep API contracts; do the capping client-side or via optional query params.

**H8. Admin "Account Security" widgets can act on the wrong user (`admin_dashboard.py`)**
- Widget keys `mod_role_select`, `mod_active_check`, `mod_reason_input`, `risky_confirm_input` are shared across targets; switching target can leave the previous user's role/active state in the widgets, then "Apply" patches the newly selected user with stale values.
- Also `["Candidate","Recruiter","Admin"].index(job_title)` raises `ValueError` for legacy roles (e.g., retired "HR Manager") and crashes the page.
- Fix: suffix every key with the target `user_id`; use a safe index fallback (0) when the role is not in the list.

**H9. Admin Backup and CSV are fetched on every rerun**
- `_show_platform_settings_and_backup` calls `/api/admin/backup` on every Streamlit rerun: downloads the whole DB each time and writes a `backup_database` audit row per page view/toggle. `_show_audit_log` also fetches the CSV on every rerun.
- Fix: fetch on demand (button "Prepare backup" stores bytes in `st.session_state`, then show `st.download_button`); same on-demand pattern for the CSV. Optionally use `sqlite3` online backup API server-side so the snapshot is consistent.

**H10. "Public Candidate Registration" toggle does nothing**
- `/api/auth/register` never checks `registration_open`. Fix: read `settings_store.get_setting(db, "registration_open")`; if `"false"`, audit `register_failure` and return 403 with a clear message. Hide/disable the Create Account button in the UI when closed (the public `/api/settings` already exposes it).

**H11. Soft-delete inconsistencies**
- `upload_candidate` and `create_candidate_and_pipeline` match existing candidates by email *including soft-deleted rows*, update them, never clear `deleted_at`, and the candidate stays invisible.
- `delete_candidate` soft-deletes the candidate but **hard-deletes** Application/InterviewSession/ResumeAnalysis/PracticeAnswer rows, so Admin "Restore" brings back a ghost with no pipeline record.
- Fix: exclude soft-deleted rows in those lookups (or clear `deleted_at` only when intentionally re-adding). `restore_candidate` must recreate a default `new` Application (with history entry) if none exists. Check `tests/test_integrity_and_security.py` for cascade-delete assertions first; keep the delete semantics the tests require and make restore self-healing rather than changing the delete design.

**H12. Long passwords crash registration**
- `bcrypt` 5.x raises `ValueError` for passwords over 72 bytes; `hash_password` is unguarded, so register/admin-create returns HTTP 500.
- Fix: validate in `UserCreate.password_strength` (max 72 UTF-8 bytes, clear message) and guard `hash_password`; list `bcrypt` explicitly in `requirements.txt` (the code imports it directly; `passlib` is unused).

**H13. Inconsistent backend URL / slow requests**
- `app.py` uses `http://localhost:8000`, `ui_common.py` uses `http://127.0.0.1:8000`. On Windows `localhost` resolves to `::1` first while uvicorn listens on IPv4, adding multi-second delays per request.
- Fix: single `API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")` used everywhere (including `_safe_fetch_file` and the "Cannot connect" message).

### B. Medium severity

- **M1. Dashboard shows fabricated/incorrect numbers (`app.py`)**: "Hiring Funnel" uses hard-coded 72%/38%/16%/5% of total; replace with real counts from `/api/pipeline` (`counts`). "Active Positions" counts closed jobs, so filter `status == "open"`. Job Matcher defaults missing hiring score to a made-up 70.0, so use the real score or hide the blend. Normalize job `status` to lowercase on create/update in `api.py` (candidate portal filters `== "open"`; "Open" would vanish).
- **M2. Recruiter Activity "Candidates Uploaded" is always 0 (`admin_routes.py`)**: it counts `Candidate.user_id == recruiter` (that FK links a candidate to its own login). Set `recruiter_id=_user.user_id` when the upload endpoint creates its Application, and count distinct `Application.candidate_id` by `recruiter_id`.
- **M3. Validation errors render as raw lists**: FastAPI 422 `detail` is a list; both `api_request` copies return it as `error` and `st.error` prints a Python repr. Join messages into readable text.
- **M4. Unescaped dynamic HTML**: candidate names/emails/skills (from resumes), job titles, notes, interview text, LLM output and the maintenance banner are interpolated into `st.markdown(..., unsafe_allow_html=True)`. Names containing `<`, `&` break layout and allow HTML injection. Add an `_esc()` helper (`html.escape`) and apply to every dynamic value in HTML f-strings in `app.py` and `admin_dashboard.py`.
- **M5. Pipeline profile drawer prints raw dicts**: education/experience/projects are lists of dicts; show `item.get("raw")` (fallback to str), as the Candidate drawer already does.
- **M6. Broken HTML wrappers**: `<div class='sh-drawer-body'>` opened in one `st.markdown` and closed in another does not wrap widgets. Use `st.container(border=True)` styled equivalently.
- **M7. Kanban "Move to..." selectbox keeps its last value** after a move (key `pipe_move_{id}` persists, so it shows the target stage instead of "Move to..."). Reset or version the key after a successful move.
- **M8. Silent failures / unguarded service calls**: recruiter "Start New Interview Session" ignores errors from create and from the opening `respond` call; Candidate "Start Mock Interview" with no jobs posts `job_id=None` and gets a 422; `complete_candidate_mock_interview`, `analyze_candidate_resume`, `evaluate_practice_answer` can raise unhandled (only some endpoints convert `RuntimeError` to 502). Show `st.error` on failure, disable start when no jobs exist, wrap those service calls the same way as the others.
- **M9. Candidate-private mock interviews visible to recruiters** (`list_interview_sessions`, `get_pipeline_application_detail` return every session including ones created by the candidate in the portal). README promises candidate isolation. Check `docs/permission_matrix.md`; if confirmed, exclude self-service sessions (created by a Candidate-role user) from recruiter views.
- **M10. `init_db` hygiene**: runs twice per start (module import + lifespan) plus in `data_ingest`; the "ensure an application per candidate" backfill does N+1 queries on every start (slow with 9.5k rows; replace with one `INSERT ... SELECT ... WHERE NOT EXISTS`); `data_ingest.seed_database` never backfills Applications after seeding (call `init_db()` at the end so seeded candidates appear in the pipeline without a restart); `--force` should also delete related Applications.
- **M11. SQLite concurrency**: no `busy_timeout`/WAL, so "database is locked" under simultaneous uploads/telemetry writes. Enable `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000` via a connect event.
- **M12. Missing `deleted_at` filters**: `get_candidate_hiring_score`, `get_candidate_skill_gap`, `get_candidate_development_report` (+export), `update_candidate_stage_direct`, `add_application_to_pipeline` can operate on soft-deleted candidates. Add the filter (404).
- **M13. State leakage on sign-out**: recruiter sign-out only pops 4 keys, so `pipeline_profile_app_id`, `show_pipeline_add_modal`, `quick_match_res`, `job_match_*`, etc. survive to the next login. Clear all session keys except `theme` on sign-out and on `_handle_unauthorized`.
- **M14. Expensive work on every rerun**: `get_cached_candidates` computes a hiring score for up to 20,000 candidates every 60 s and pulls full records; `_safe_fetch_file` fetches CSV and DOCX exports on every render of Skill Gap; `/api/settings` is fetched every rerun; speech recognition (network call) re-runs each rerun on the same audio. Cache by audio hash, fetch exports on demand, cache settings briefly, request only the fields needed.
- **M15. Pipeline "Upload & Register New Candidate" glitch**: typed name/email/phone are discarded (the parser's values are used); the upload already creates an `Application`, so the follow-up `POST /api/pipeline/applications` creates a duplicate (job selected) or errors silently (no job), and the chosen stage is ignored. Fix flow without adding endpoints: after upload, if no job selected, PATCH the stage of the existing application; surface errors; tell the user that parsed resume details are used.
- **M16. Cosmetic data glitches**: Candidates sort "Recent" does nothing (sort by `candidate_id`/`created_at` desc); `/api/analytics/skills` applies `.title()` to lower-cased skills so "AWS" becomes "Aws", "SQL" becomes "Sql", "NLP" becomes "Nlp" (keep a display-casing map or uppercase known acronyms).
- **M17. Auth hardening without behavior change**: login returns the retired-role 403 *before* verifying the password (account/role enumeration); verify the password first. Restrict CORS origins via env (wildcard + credentials is invalid per spec).

### C. Low severity / hygiene
- `st.success(...)` immediately followed by `st.rerun()` is never seen; use `st.toast` or store a flash message in session state (admin user update, job update, purge, settings save).
- Unused imports (`wave`, `urllib.parse`, `go`, `ValidationError`, etc.); `load_css()` is called twice for the candidate dashboard.
- `app.py` duplicates `render_svg`, `api_request`, `_handle_unauthorized`, `get_plotly_layout` from `ui_common.py` (drift risk; the two `api_request`s already differ). Optional: import from `ui_common` and add the icons only `app.py` has (plus, trash, download, mic, volume, mail, phone, clock, award) to the shared set.
- `AdminUserCreate` does no email-format validation; add the same check `UserCreate` uses.
- `pyttsx3` engine re-initialised per call and can throw "run loop already started"; guard with a lock and fall back gracefully.
- README/requirements: add `python -m spacy download en_core_web_sm` (parser silently degrades to regex without it), confirm `.env.example` exists and lists all vars, note Linux needs `espeak` for `pyttsx3`.

### D. Decisions needed (apply the safe option, then ask)
1. README says Admin sees "aggregates and metadata only, never candidate personal data", yet Data Health returns candidate name/email and `restore_candidate` returns a full `CandidateResponse`. Safe option: return only id, name initials/ID and counts to Admin; restore returns a minimal message. Confirm the intended policy.
2. M9 (recruiters seeing candidates' private mock interviews): confirm intended visibility.
3. Should `delete_candidate` stay "soft-delete candidate + hard-delete children"? Fix restore either way (H11).

### E. Unverified: Phase 4 must check these in `services/*`
- `hiring_score.calculate_hiring_score` return keys: the API maps flat keys (`resume_completeness_score`, ...) while the UI drawer reads `["component_scores"]`; make them agree (the drawer's 5-pillar panel is empty otherwise). `blend_with_job_match` must accept `hiring_weight` (UI) and `hiring_score=`/`job_match_final_score=` (API).
- `matching_engine.score_candidate` signature and result keys (see H3); consistent use of `skill_taxonomy.normalize_skill`.
- `llm_client`: every call writes an `LlmUsage` row with `feature`, `latency_ms`, `success`, and the calling `user_id` (Admin AI Monitor's "Top 10" depends on it); timeouts, retries and clean `RuntimeError` on provider failure; no key leakage in logs or errors; behavior when `SARVAM_API_KEY` is missing.
- `audit.log_event`: never raises, accepts a `User` or a string actor, and does not commit half of a caller's transaction (`delete_candidate` logs before its own commit).
- `settings_store`: `DEFAULT_SETTINGS` keys match the admin UI keys; boolean strings are normalized.
- `candidate_service`: returned dict shapes match what `app.py` reads (`ats_feedback.ats_score`, `strengths`, `improvement_areas`, `competency_scores`, `overall_score`, `verdict`, `score`, `evaluation_summary`, `model_answer`), with fallbacks when the LLM is down.

---

## 3. IMPLEMENTATION PLAN

| Phase | Goal | Lead | Flash handles |
|---|---|---|---|
| 0 | Baseline | Anti Gravity | Run installs, collect pytest output |
| 1 | Startup and environment (H1, H4, H12, H13, M10, M11, requirements/README) | Anti Gravity | requirements pin, README, `.env.example` |
| 2 | Backend correctness (H3, H6, H10, H11, M1 status, M2, M8, M12, M17) | Anti Gravity | Regression tests per fix |
| 3 | Frontend (H2, H5, H7, H8, H9, M1, M3 to M7, M13 to M16, Low) | Anti Gravity (H2, H7, H8, H9, M15) | `_esc()` rollout (M4), `width="stretch"` migration, flash messages |
| 4 | Services audit (section E) and second-pass sweep | Anti Gravity | Unit tests for service return shapes |
| 5 | Tests and smoke verification | Anti Gravity | Test authoring, CHANGELOG_FIXES.md |

### Phase 0: Baseline
1. `git checkout -b fix/stabilization`; fresh venv; `pip install -r requirements.txt`; `python -m spacy download en_core_web_sm`.
2. Copy `.env.example` to `.env` with test values (never reuse the exposed key). Set `BOOTSTRAP_ADMIN_EMAIL/PASSWORD`.
3. `pytest tests/ -v`; save the baseline. Read `services/*`, `tests/*`, `docs/permission_matrix.md`.
4. Back up `smarthire.db` before any migration-related change.

### Phase 1: Startup and environment
- H1: `import env_loader` in `database.py`; log instead of swallow; document env vars.
- H4: rewrite `run.py` launch commands (`sys.executable`, inherit stdout, portable).
- H12: password max-bytes validation and explicit `bcrypt` dependency.
- H13: shared `API_BASE_URL` (env, default `127.0.0.1`).
- M10: single backfill query, call `init_db()` at the end of seeding, `--force` cleans Applications.
- M11: WAL + busy timeout.
- Verify: delete `smarthire.db`, run `python run.py`, confirm bootstrap admin can log in; confirm backend survives sustained request logging.

### Phase 2: Backend
- H3 helper `_pipeline_match_score` and 5 call-site replacements.
- H6: store saved filenames; data-health exclusions.
- H10: enforce `registration_open`.
- H11: soft-delete-aware lookups; restore recreates the Application.
- M2: set `recruiter_id` on upload applications; fix admin counting query.
- M1: lowercase job status; M8: wrap services in 502 handling; M12: `deleted_at` filters; M17: password-before-role-check, env-driven CORS.
- Verify: pytest plus new tests (below).

### Phase 3: Frontend
- H2 dedup fix; H7 pagination/caps; H8 per-user keys and safe index; H9 on-demand backup/CSV.
- H5 compatibility pass against the installed Streamlit; pin the version.
- M1 real funnel and open-job count; M3 error formatter; M4 `_esc()` everywhere; M5, M6, M7; M8 UI error surfacing; M13 sign-out clear; M14 caching/on-demand fetching; M15 upload flow; M16 sort and casing; Low items.
- Verify by clicking through each role (section 6).

### Phase 4: Services audit
- Walk section E; align return shapes with consumers; fix without changing behavior; add shape tests with the LLM mocked.

### Phase 5: Tests and release check
New regression tests (at minimum): bootstrap admin from env; registration closed returns 403; password >72 bytes returns 422 (not 500); pipeline `match_score` non-null when a job is attached; upload stores real filename and data-health reports no false Missing/Orphan; soft-deleted candidate not resurrected by upload and restore recreates Application; recruiter activity counts uploads; job status normalization; dedup helper keeps all nameless candidates; admin user-update with legacy role does not crash; backup endpoint writes exactly one audit row per explicit call.

---

## 4. Guardrails for the agents (restate in every sub-task)
- Smallest possible diff; no refactors beyond what a fix needs.
- Do not touch the feature set, route paths, response shapes, DB columns, theme/CSS design (other than selector compatibility in H5).
- No new dependencies except `bcrypt` (explicit) and version pins.
- Never log, print, commit or paste secrets or password hashes.
- If a fix conflicts with an existing test, stop and report before changing the test.

## 5. Definition of done
- `pytest tests/ -v` is green (baseline count plus new tests).
- Fresh DB + `python run.py` starts both servers with no tracebacks or Streamlit deprecation errors.
- No console errors during the smoke test; no `except: pass` left that hides a failure.
- `CHANGELOG_FIXES.md` lists every fix (ID, file, one-line root cause) and every open decision.

## 6. Manual smoke test (run after all phases)
1. **Admin**: log in with the bootstrap admin; Command Center loads; provision a Recruiter and a Candidate (temp passwords shown); change a role with a reason, confirm the right user changed; switch target user and confirm the widgets reset; Data Governance shows no false Missing/Orphan; purge preview and execute with the typed phrase, restore one candidate and confirm it reappears in the recruiter pipeline; Audit Log filters and CSV; Settings toggles take effect (including closing registration); backup is only fetched on click and creates one audit row.
2. **Recruiter**: seed or upload resumes; Candidates page paginates and shows all seeded rows; create a job (open/closed counts correct); Job Matcher ranks (top N shown, no hang); Pipeline shows match scores, move a card across stages, open a profile (readable education/experience), add a candidate (existing and new); Interview simulation start/respond/conclude with visible errors if the LLM is down; Analytics and Skill Gap (exports on demand).
3. **Candidate**: register (and confirm closed registration blocks it), upload resume, run ATS audit, practice questions (open and MCQ), mock interview start/respond/complete, history; confirm no recruiter or admin data is reachable.
4. Sign out and sign in as another role; confirm no leftover state; confirm session-expiry flow returns to login cleanly.
