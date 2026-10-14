# SmartHire AI — Permission & Role Access Control Matrix

This document defines the strict role separation and authorization boundaries implemented across SmartHire AI. Every API endpoint and frontend interface enforces discrete access control based on user identity. No endpoint or view is shared between roles.

---

## 👥 Role Definitions & Responsibilities

| Role | Responsibility | Scope of Access | Restrictions |
| :--- | :--- | :--- | :--- |
| **Admin** | Platform governance, user lifecycle management, data health, security audit trails, AI telemetry, system settings. | `/api/admin/*`, `/api/auth/*`, and the dedicated Admin Control Plane (`admin_dashboard.py`). | **Aggregates & metadata only.** Strictly forbidden from viewing candidate resume text, personal candidate details, recruiter pipelines, job creation, or candidate portal features. |
| **Recruiter** | Talent acquisition, candidate sourcing, ATS Kanban pipeline movement, job specifications, skill gap analysis, recruiter interview prep. | `/api/candidates/*`, `/api/jobs/*`, `/api/pipeline/*`, `/api/analytics/*`, `/api/interview-sessions/*`, `/api/match`, Recruiter ATS (`app.py`). | Strictly forbidden from administrative controls, user management, audit logs, AI telemetry, candidate portal endpoints, or hard data purging. |
| **Candidate** | Personal profile management, resume upload, AI ATS compatibility diagnostics, interactive practice questions, adaptive AI mock interviews. | `/api/candidate/*`, `/api/auth/*`, Candidate Portal (`app.py`). | Strictly forbidden from viewing other candidates' data, recruiter job administration, matching engines, or administrative APIs. |
| **Public / Unauthenticated** | Candidate self-registration, user authentication, and system health status. | `/api/auth/register`, `/api/auth/login`, `/api/settings`, `/docs`, `/openapi.json`. | Public registration is restricted strictly to `Candidate` accounts; creation of `Recruiter` and `Admin` accounts is blocked with HTTP 403. |

> [!IMPORTANT]
> **Hiring & Talent Acquisition Work Notice**:
> All talent acquisition and hiring activities (posting jobs, uploading candidate resumes, moving applications across ATS Kanban stages, running candidate-job matches, and conducting recruiter interview prep) **strictly require an active Recruiter account**. Administrators cannot perform recruitment workflows, and recruiters cannot perform platform governance.

---

## 🔐 API Authorization Matrix

### 1. Authentication & System Endpoints

| HTTP Method | Route | Public | Candidate | Recruiter | Admin | Description |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `POST` | `/api/auth/register` | ✅ (Candidate only) | ❌ | ❌ | ❌ | Public self-service registration. Attempts to register as Recruiter or Admin are rejected with `403 Forbidden`. |
| `POST` | `/api/auth/login` | ✅ | ✅ | ✅ | ✅ | Authenticate with email, password, and optional `role` ("Candidate", "Recruiter", "Admin") to receive a Bearer JWT. Mismatched roles return `403 Forbidden`. |
| `GET` | `/api/auth/me` | ❌ | ✅ | ✅ | ✅ | Return current authenticated user profile. |
| `GET` | `/api/auth/profile` | ❌ | ❌ (403) | ✅ | ✅ | Retrieve authenticated recruiter or admin profile details. |
| `PUT` | `/api/auth/profile` | ❌ | ❌ (403) | ✅ | ✅ | Update authenticated recruiter or admin profile (`full_name`, `company_name`, `phone_number`). Audited as `update_profile`. |
| `POST` | `/api/auth/change-password` | ❌ | ❌ (403) | ✅ | ✅ | Change authenticated recruiter or admin password with current password verification. Audited as `change_password`. |
| `GET` | `/api/settings` | ✅ | ✅ | ✅ | ✅ | Public platform flags (`registration_open`, `feature_mock_interview`, etc.) and system maintenance banner. |
| `GET` | `/docs`, `/openapi.json`, `/redoc` | ✅ | ✅ | ✅ | ✅ | OpenAPI documentation and Swagger UI. |

---

### 2. Administrator Endpoints (`/api/admin/*`)
*Protected by `require_admin`. Any request from a `Recruiter` or `Candidate` receives **`HTTP 403 Forbidden`** and logs an `access_denied` audit event.*

| HTTP Method | Route | Candidate | Recruiter | Admin | Description |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `GET` | `/api/admin/overview` | ❌ (403) | ❌ (403) | ✅ | Platform summary metrics (user counts, active 7/30d, job counts, candidate totals, DB size, upload size). |
| `GET` | `/api/admin/users` | ❌ (403) | ❌ (403) | ✅ | User management list with filters (`q`, `role`, `status`) and pagination. |
| `PATCH` | `/api/admin/users/{user_id}` | ❌ (403) | ❌ (403) | ✅ | Modify user role or active status with mandatory audit reason. Self-demotion and last-admin lock enforced. |
| `POST` | `/api/admin/users` | ❌ (403) | ❌ (403) | ✅ | Provision new user with auto-generated temporary password returned once. |
| `POST` | `/api/admin/users/{user_id}/reset-password` | ❌ (403) | ❌ (403) | ✅ | Reset a user's password and return one-time temporary credentials. |
| `GET` | `/api/admin/audit-logs` | ❌ (403) | ❌ (403) | ✅ | Query security audit log records with filtering and optional CSV download. |
| `GET` | `/api/admin/data-health` | ❌ (403) | ❌ (403) | ✅ | Data integrity scans (duplicate emails, empty skills, orphan files, missing resumes). |
| `POST` | `/api/admin/candidates/purge` | ❌ (403) | ❌ (403) | ✅ | Permanently purge soft-deleted candidates by ID list with confirmation. |
| `POST` | `/api/admin/candidates/{candidate_id}/restore` | ❌ (403) | ❌ (403) | ✅ | Restore a soft-deleted candidate back into the active pool. |
| `GET` | `/api/admin/jobs` | ❌ (403) | ❌ (403) | ✅ | Platform-wide job listing with creator metadata and status filters. |
| `PATCH` | `/api/admin/jobs/{job_id}` | ❌ (403) | ❌ (403) | ✅ | Administrative job status toggle and creator reassignment. |
| `GET` | `/api/admin/recruiters/activity` | ❌ (403) | ❌ (403) | ✅ | Recruiter productivity audits (candidates added, jobs posted, interviews handled). |
| `GET` | `/api/admin/ai-usage` | ❌ (403) | ❌ (403) | ✅ | AI telemetry metrics (latency percentiles, error rates, model call volumes, top consumers). |
| `GET` | `/api/admin/settings` | ❌ (403) | ❌ (403) | ✅ | Internal administrative feature flag and maintenance settings view. |
| `PUT` | `/api/admin/settings` | ❌ (403) | ❌ (403) | ✅ | Update platform feature flags and system maintenance banner text. |
| `GET` | `/api/admin/backup` | ❌ (403) | ❌ (403) | ✅ | Stream full SQLite database file snapshot as an attachment download. |

---

### 3. Candidate Portal Endpoints (`/api/candidate/*`)
*Protected by `require_candidate`. Any request from an `Admin` or `Recruiter` receives **`HTTP 403 Forbidden`** and logs an `access_denied` audit event.*

| HTTP Method | Route | Candidate | Recruiter | Admin | Description |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `GET` | `/api/candidate/jobs` | ✅ | ❌ (403) | ❌ (403) | Fetch open jobs available for candidate benchmark scoring and mock interview alignment. |
| `GET` | `/api/candidate/profile` | ✅ | ❌ (403) | ❌ (403) | Retrieve caller's personal candidate profile and skill records. |
| `PUT` | `/api/candidate/profile` | ✅ | ❌ (403) | ❌ (403) | Update caller's personal contact details, skills, experience, and education. |
| `POST` | `/api/candidate/resume/upload` | ✅ | ❌ (403) | ❌ (403) | Upload resume document (`.pdf`, `.docx`, `.txt`) for automated profile parsing. |
| `POST` | `/api/candidate/resume/analyze` | ✅ | ❌ (403) | ❌ (403) | Run 10-dimension AI resume audit, ATS score calculation, and role alignment. |
| `GET` | `/api/candidate/resume/analysis` | ✅ | ❌ (403) | ❌ (403) | Retrieve existing AI resume analysis report for the caller. |
| `GET` | `/api/candidate/practice-questions` | ✅ | ❌ (403) | ❌ (403) | Fetch structured practice interview questions by category, difficulty, and format. |
| `POST` | `/api/candidate/practice-answers` | ✅ | ❌ (403) | ❌ (403) | Submit practice answer and receive constructive AI feedback and STAR exemplar. |
| `GET` | `/api/candidate/practice-history` | ✅ | ❌ (403) | ❌ (403) | Retrieve caller's historical practice attempts and feedback reports. |
| `POST` | `/api/candidate/mock-interview/start` | ✅ | ❌ (403) | ❌ (403) | Launch adaptive AI mock interview session with dynamic initial question. |
| `POST` | `/api/candidate/mock-interview/{session_id}/respond` | ✅ | ❌ (403) | ❌ (403) | Submit candidate conversational response turn in active mock interview room. |
| `POST` | `/api/candidate/mock-interview/{session_id}/complete` | ✅ | ❌ (403) | ❌ (403) | End mock interview, calculate overall score, and generate comprehensive evaluation. |
| `GET` | `/api/candidate/mock-interviews` | ✅ | ❌ (403) | ❌ (403) | List all past mock interview sessions belonging to the caller. |
| `GET` | `/api/candidate/mock-interviews/{session_id}` | ✅ | ❌ (403) | ❌ (403) | Retrieve full transcript, competency breakdown, and report for specific mock session. |

---

### 4. Recruiter Endpoints (ATS Pipeline, Candidate Pool, Jobs, Analytics)
*Protected by `require_recruiter`. Any request from an `Admin` or `Candidate` receives **`HTTP 403 Forbidden`** and logs an `access_denied` audit event.*

| HTTP Method | Route | Candidate | Recruiter | Admin | Description |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `POST` | `/api/candidates/upload` | ❌ (403) | ✅ | ❌ (403) | Upload and parse candidate resume into talent acquisition pool. |
| `GET` | `/api/candidates` | ❌ (403) | ✅ | ❌ (403) | Query candidate pool with search query, stage filter, and pagination (excludes soft-deleted). |
| `GET` | `/api/candidates/hiring-scores` | ❌ (403) | ✅ | ❌ (403) | Retrieve composite hiring scores across all active candidates. |
| `GET` | `/api/candidates/{candidate_id}` | ❌ (403) | ✅ | ❌ (403) | Fetch complete candidate record, parsed skills, and timeline. |
| `GET` | `/api/candidates/{candidate_id}/hiring-score` | ❌ (403) | ✅ | ❌ (403) | Fetch detailed hiring score component breakdown for a candidate. |
| `PATCH` | `/api/candidates/{candidate_id}/stage` | ❌ (403) | ✅ | ❌ (403) | Update candidate recruitment pipeline stage directly. |
| `DELETE` | `/api/candidates/{candidate_id}` | ❌ (403) | ✅ | ❌ (403) | Soft-delete candidate from recruiter talent pool (`deleted_at` timestamp). |
| `DELETE` | `/api/candidates` | ❌ (403) | ❌ (400) | ❌ (403) | Bulk candidate deletion guard (returns 400 Bad Request to recruiters). |
| `POST` | `/api/jobs` | ❌ (403) | ✅ | ❌ (403) | Create a new job requisition. |
| `GET` | `/api/jobs` | ❌ (403) | ✅ | ❌ (403) | List job postings with optional status filtering. |
| `GET` | `/api/jobs/{job_id}` | ❌ (403) | ✅ | ❌ (403) | Retrieve job posting details and requirement specifications. |
| `PUT` | `/api/jobs/{job_id}` | ❌ (403) | ✅ | ❌ (403) | Update job posting description, requirements, or status. |
| `DELETE` | `/api/jobs/{job_id}` | ❌ (403) | ✅ | ❌ (403) | Delete job posting and associated match records. |
| `POST` | `/api/jobs/{job_id}/match` | ❌ (403) | ✅ | ❌ (403) | Run multi-factor matching engine against candidate pool for target job. |
| `POST` | `/api/match` | ❌ (403) | ✅ | ❌ (403) | Match candidates against arbitrary job requirements. |
| `GET` | `/api/jobs/{job_id}/skill-gap-report` | ❌ (403) | ✅ | ❌ (403) | Compute talent pool skill coverage and critical deficit metrics for job. |
| `GET` | `/api/jobs/{job_id}/skill-gap-report/candidates/{candidate_id}` | ❌ (403) | ✅ | ❌ (403) | Compute individual candidate skill gap against job. |
| `GET` | `/api/jobs/{job_id}/skill-gap-report/candidates/{candidate_id}/development-report` | ❌ (403) | ✅ | ❌ (403) | Generate candidate targeted development plan. |
| `GET` | `/api/jobs/{job_id}/skill-gap-report/candidates/{candidate_id}/development-report/export` | ❌ (403) | ✅ | ❌ (403) | Export individual development report file. |
| `GET` | `/api/jobs/{job_id}/skill-gap-report/development-reports/batch-export` | ❌ (403) | ✅ | ❌ (403) | Batch export candidate development reports. |
| `GET` | `/api/jobs/{job_id}/skill-gap-report/export` | ❌ (403) | ✅ | ❌ (403) | Export job skill gap report as CSV or DOCX. |
| `GET` | `/api/jobs/{job_id}/interview-questions` | ❌ (403) | ✅ | ❌ (403) | Generate structured recruiter interview question guides. |
| `GET` | `/api/jobs/{job_id}/interview-questions/practice` | ❌ (403) | ✅ | ❌ (403) | Generate practice question sets for job context. |
| `GET` | `/api/pipeline` | ❌ (403) | ✅ | ❌ (403) | Fetch 6-stage Kanban board applications, stages, and metrics. |
| `POST` | `/api/pipeline/applications` | ❌ (403) | ✅ | ❌ (403) | Add candidate application to recruitment pipeline. |
| `GET` | `/api/pipeline/applications/{application_id}` | ❌ (403) | ✅ | ❌ (403) | Fetch pipeline application details and history. |
| `PATCH` | `/api/pipeline/applications/{application_id}/stage` | ❌ (403) | ✅ | ❌ (403) | Transition application between pipeline stages. |
| `PATCH` | `/api/pipeline/applications/{application_id}/notes` | ❌ (403) | ✅ | ❌ (403) | Append or update recruiter evaluation notes. |
| `POST` | `/api/pipeline/candidates` | ❌ (403) | ✅ | ❌ (403) | Create candidate and initial application in one atomic step. |
| `GET` | `/api/analytics/summary` | ❌ (403) | ✅ | ❌ (403) | Recruiter pipeline analytics overview. |
| `GET` | `/api/analytics/skills` | ❌ (403) | ✅ | ❌ (403) | Distribution of extracted technical skills across active candidates. |
| `POST` | `/api/interview-sessions` | ❌ (403) | ✅ | ❌ (403) | Create recruiter interview session. |
| `GET` | `/api/interview-sessions` | ❌ (403) | ✅ | ❌ (403) | List recruiter interview sessions. |
| `GET` | `/api/interview-sessions/{session_id}` | ❌ (403) | ✅ | ❌ (403) | Fetch recruiter interview session details and transcript. |
| `POST` | `/api/interview-sessions/{session_id}/respond` | ❌ (403) | ✅ | ❌ (403) | Submit turn in recruiter interview assistant session. |
| `POST` | `/api/interview-sessions/{session_id}/complete` | ❌ (403) | ✅ | ❌ (403) | Finalize recruiter interview assistant session. |

---

## 🖥️ Frontend Shell Boundaries

| UI Shell | Function | File | Allowed Role | Isolation Guarantee |
| :--- | :--- | :--- | :--- | :--- |
| **Admin Control Plane** | `show_admin_dashboard(token, user)` | `admin_dashboard.py` | `Admin` | Protected by top-level session role check (`user.job_title == "Admin"`). No recruiter pages, pipeline components, or candidate profile inspection tools are imported or accessible. |
| **Recruiter ATS** | `show_recruiter_dashboard(token, user)` | `app.py` | `Recruiter` | Protected by top-level session role check (`user.job_title == "Recruiter"`). No administrative navigation, user governance, audit trail inspection, or database purge tools are present. |
| **Candidate Career Hub** | `show_candidate_dashboard(token, user)` | `app.py` | `Candidate` | Protected by top-level session role check (`user.job_title == "Candidate"`). Scoped strictly to the caller's candidate record; cannot view other candidates or recruiter workflows. |

---

## 🛡️ Security & Auditing Guarantees

1. **No Shared Roles**: No route or view uses loose union access like `"role OR Admin"`. Every endpoint declares an explicit single-role dependency (`require_admin`, `require_recruiter`, or `require_candidate`).
2. **Deterministic Cross-Role Rejection**: When an authenticated user requests a route outside their role boundary, FastAPI raises `HTTP 403 Forbidden` (no route hiding via 404).
3. **Audited Access Denials**: Every blocked cross-role request automatically logs an `access_denied` record in `AuditLog` containing the actor ID, actor email, attempted action, and required roles.
4. **Self-Governance Locks**: Administrators cannot demote themselves or deactivate their own accounts, and the last active Administrator cannot be demoted or deactivated under any circumstance.
