# Changelog: Role-Checked Login & Profile Management

## Overview
This release implements strict role enforcement at login, candidate-only self-registration, admin-exclusive account provisioning, and personalized profile management for Recruiter and Admin roles without breaking existing API contracts, database schemas, or themes.

---

### 1. Role-Checked Sign-in
- **Backend (`schemas.py`, `api.py`)**:
  - `UserLogin` model updated with optional `role: Optional[str] = None`.
  - Field validator normalizes role case-insensitively to `"Candidate"`, `"Recruiter"`, `"Admin"` or raises 422 for unrecognized values.
  - In `api.py:login()`, after verifying credentials and account active status, role alignment is enforced: if `payload.role` is provided and does not match the user's registered `job_title`, returns HTTP 403 Forbidden with `f"This account is not registered as a {payload.role}. Select the correct role to sign in."` and logs an audit row with `action="login_failure"`, `reason="role_mismatch"`.
  - Password verification precedes role checks to prevent role discovery timing attacks.
  - Omitting `role` maintains full backward compatibility for existing API clients and automated tests.
- **Frontend (`app.py`)**:
  - `show_login()` renders a horizontal role radio selector (`Candidate`, `Recruiter`, `Admin`, default `Candidate`) with guidance caption.
  - Sends chosen `role` in the authentication request.

### 2. Candidate-Only Self-Registration
- **Backend (`api.py`)**:
  - Validates `payload.job_title` strictly equals `"Candidate"`. Attempts to register with privileged roles (`Recruiter`, `Admin`) return HTTP 403 Forbidden with `f"{role} accounts must be created by an administrator."` and write an audit log row.
  - Honors `registration_open` platform setting (returns 403 when set to `"false"`).
- **Frontend (`app.py`)**:
  - Replaced the selectbox with a disabled `Account Type: Candidate` indicator and explanatory caption ("Recruiter and Admin accounts are created by an administrator.").

### 3. Admin-Exclusive Account Provisioning Hardening
- **Backend (`admin_routes.py`, `schemas.py`)**:
  - Confirmed `POST /api/admin/users` is the only route permitted to provision `Recruiter` and `Admin` users.
  - Validates email format with regex and enforces case-insensitive email deduplication.
  - Protects bootstrap admin account and prevents non-admin execution with 403 Forbidden.

### 4. My Profile for Recruiter & Admin
- **Backend (`api.py`, `schemas.py`)**:
  - Added `GET /api/auth/profile` and `PUT /api/auth/profile` protected by `require_roles("Recruiter", "Admin")` (Candidate requests return 403 with `access_denied` audit entry).
  - Added `ProfileUpdate` Pydantic model (`model_config = ConfigDict(extra="forbid")`) validating `full_name`, `company_name`, and `phone_number`. Forbids changes to `email`, `job_title`, `role`, `is_active`, or `user_id` with HTTP 422.
  - Added `POST /api/auth/change-password` requiring current password verification and password strength checks.
  - Profile modifications and password updates log `update_profile` and `change_password` audit trail records.
- **Frontend (`ui_common.py`, `app.py`, `admin_dashboard.py`)**:
  - Added `render_profile_page(token, user, role_label)` in `ui_common.py` displaying read-only account metadata and an editable profile form with instant state update and toast alerts.
  - Added "My Profile" button under the Workspace group in `show_recruiter_dashboard` (`app.py`).
  - Added "My Profile" button under the new Account group in `show_admin_dashboard` (`admin_dashboard.py`).
  - Added `"update_profile"` and `"change_password"` to audit log action filter choices in `admin_dashboard.py`.

---

### 5. Automated Test Coverage
- Created `tests/test_role_login_and_profile.py` containing 18 comprehensive tests.
- Full test suite verified green: **159 passing tests**.
