"""
tests/test_role_login_and_profile.py — Comprehensive tests for Role-Checked Sign-in,
Profile Management, Password Change, and Admin Provisioning Hardening.
"""

import pytest
from fastapi.testclient import TestClient

from api import app
from database import SessionLocal
from models import User, AuditLog, PlatformSetting
from auth import hash_password, create_access_token


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def seed_users():
    """Ensure test users for Candidate, Recruiter, and Admin exist with known passwords."""
    db = SessionLocal()
    users_data = [
        ("Candidate User", "test_candidate_rlp@example.com", "Candidate", "CandidatePass123!"),
        ("Recruiter User", "test_recruiter_rlp@example.com", "Recruiter", "RecruiterPass123!"),
        ("Admin User", "test_admin_rlp@example.com", "Admin", "AdminPass123!"),
        ("Disabled Recruiter", "test_disabled_rlp@example.com", "Recruiter", "DisabledPass123!"),
    ]
    created = {}
    for name, email, role, pwd in users_data:
        u = db.query(User).filter(User.email == email).first()
        if not u:
            u = User(
                full_name=name,
                email=email,
                password_hash=hash_password(pwd),
                company_name="TestCorp",
                job_title=role,
                is_active=(role != "Disabled Recruiter" and "Disabled" not in name),
            )
            db.add(u)
            db.commit()
            db.refresh(u)
        else:
            u.full_name = name
            u.job_title = role
            u.password_hash = hash_password(pwd)
            u.is_active = ("Disabled" not in name)
            db.commit()
            db.refresh(u)
        created[role.lower() if "Disabled" not in name else "disabled"] = {
            "email": email,
            "password": pwd,
            "user_id": u.user_id,
        }
    db.close()
    return created


# ===========================================================================
# Phase 1: Role-Checked Login Tests
# ===========================================================================

def test_login_matching_role_succeeds(client, seed_users):
    """Signing in with the correct role returns 200 and access token."""
    for role in ["Candidate", "Recruiter", "Admin"]:
        data = seed_users[role.lower()]
        resp = client.post(
            "/api/auth/login",
            json={"email": data["email"], "password": data["password"], "role": role},
        )
        assert resp.status_code == 200, f"Expected 200 for {role}, got {resp.status_code}: {resp.text}"
        res_json = resp.json()
        assert "access_token" in res_json
        assert res_json["user"]["job_title"] == role


def test_login_role_case_insensitive_normalization(client, seed_users):
    """Role validator normalizes lowercase or mixed case roles."""
    data = seed_users["candidate"]
    resp = client.post(
        "/api/auth/login",
        json={"email": data["email"], "password": data["password"], "role": "candidate"},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["job_title"] == "Candidate"


def test_login_omitted_role_succeeds(client, seed_users):
    """Backward compatibility: omitting the role field allows login for any valid account."""
    for role in ["candidate", "recruiter", "admin"]:
        data = seed_users[role]
        resp = client.post(
            "/api/auth/login",
            json={"email": data["email"], "password": data["password"]},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()


def test_login_all_role_mismatch_combinations_return_403(client, seed_users):
    """Every mismatched role combination returns HTTP 403, clear message, and login_failure audit log."""
    roles = ["Candidate", "Recruiter", "Admin"]
    db = SessionLocal()

    for actual_role in roles:
        data = seed_users[actual_role.lower()]
        for attempted_role in roles:
            if attempted_role == actual_role:
                continue

            resp = client.post(
                "/api/auth/login",
                json={"email": data["email"], "password": data["password"], "role": attempted_role},
            )
            assert resp.status_code == 403, (
                f"Actual {actual_role} logging in as {attempted_role} expected 403, got {resp.status_code}"
            )
            detail = resp.json().get("detail", "")
            assert f"This account is not registered as a {attempted_role}" in detail
            assert "Select the correct role to sign in." in detail

            # Verify audit log recorded
            audit_entry = (
                db.query(AuditLog)
                .filter(AuditLog.actor_email == data["email"], AuditLog.action == "login_failure")
                .order_by(AuditLog.audit_id.desc())
                .first()
            )
            assert audit_entry is not None
            assert "role_mismatch" in (audit_entry.details or "")
    db.close()


def test_login_wrong_password_does_not_reveal_role(client, seed_users):
    """Wrong password returns 401 Incorrect email or password even if role is wrong or right."""
    data = seed_users["admin"]
    # Wrong password with matching role
    resp1 = client.post(
        "/api/auth/login",
        json={"email": data["email"], "password": "WrongPassword123!", "role": "Admin"},
    )
    assert resp1.status_code == 401
    assert resp1.json()["detail"] == "Incorrect email or password."

    # Wrong password with mismatched role
    resp2 = client.post(
        "/api/auth/login",
        json={"email": data["email"], "password": "WrongPassword123!", "role": "Candidate"},
    )
    assert resp2.status_code == 401
    assert resp2.json()["detail"] == "Incorrect email or password."


def test_login_disabled_account_remains_blocked(client, seed_users):
    """Disabled account receives 403 disabled error, not role mismatch."""
    data = seed_users["disabled"]
    resp = client.post(
        "/api/auth/login",
        json={"email": data["email"], "password": data["password"], "role": "Recruiter"},
    )
    assert resp.status_code == 403
    assert "Your account is disabled" in resp.json()["detail"]


def test_login_invalid_role_returns_422(client, seed_users):
    """Unrecognized role string returns 422 Unprocessable Entity."""
    data = seed_users["candidate"]
    resp = client.post(
        "/api/auth/login",
        json={"email": data["email"], "password": data["password"], "role": "SuperAdmin"},
    )
    assert resp.status_code == 422


# ===========================================================================
# Phase 2: Profile & Password Management Endpoints
# ===========================================================================

def test_profile_read_by_recruiter_and_admin(client, seed_users):
    """Recruiter and Admin can read their profile via GET /api/auth/profile."""
    for role in ["recruiter", "admin"]:
        email = seed_users[role]["email"]
        token = create_access_token({"sub": email})
        resp = client.get("/api/auth/profile", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == email
        assert data["job_title"] == role.capitalize()
        assert "full_name" in data


def test_profile_candidate_forbidden(client, seed_users):
    """Candidate receives 403 Forbidden and access_denied audit row on /api/auth/profile."""
    email = seed_users["candidate"]["email"]
    token = create_access_token({"sub": email})
    resp = client.get("/api/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403

    db = SessionLocal()
    audit_entry = (
        db.query(AuditLog)
        .filter(AuditLog.actor_email == email, AuditLog.action == "access_denied")
        .order_by(AuditLog.audit_id.desc())
        .first()
    )
    assert audit_entry is not None
    db.close()


def test_profile_unauthenticated_returns_401(client):
    """Request without token returns 401 Unauthorized."""
    resp = client.get("/api/auth/profile")
    assert resp.status_code == 401


def test_profile_update_allowed_fields(client, seed_users):
    """Recruiter can update full_name, company_name, and phone_number with audit trail."""
    email = seed_users["recruiter"]["email"]
    token = create_access_token({"sub": email})

    update_payload = {
        "full_name": "Updated Recruiter Name",
        "company_name": "Acme Talent Corp",
        "phone_number": "+1 (555) 987-6543",
    }
    resp = client.put(
        "/api/auth/profile",
        headers={"Authorization": f"Bearer {token}"},
        json=update_payload,
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["full_name"] == "Updated Recruiter Name"
    assert res_data["company_name"] == "Acme Talent Corp"
    assert res_data["phone_number"] == "+1 (555) 987-6543"

    # Verify audit row
    db = SessionLocal()
    audit_entry = (
        db.query(AuditLog)
        .filter(AuditLog.actor_email == email, AuditLog.action == "update_profile")
        .order_by(AuditLog.audit_id.desc())
        .first()
    )
    assert audit_entry is not None
    assert "Updated Recruiter Name" in (audit_entry.details or "")
    db.close()


def test_profile_update_blank_phone_clears_to_null(client, seed_users):
    """Setting phone_number to empty string or null clears it to None."""
    email = seed_users["recruiter"]["email"]
    token = create_access_token({"sub": email})

    resp = client.put(
        "/api/auth/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"phone_number": ""},
    )
    assert resp.status_code == 200
    assert resp.json()["phone_number"] is None


def test_profile_update_forbidden_fields_return_422(client, seed_users):
    """Attempts to modify email, job_title, role, is_active, or user_id return 422."""
    email = seed_users["recruiter"]["email"]
    token = create_access_token({"sub": email})

    for bad_field in ["job_title", "email", "is_active", "user_id", "role"]:
        resp = client.put(
            "/api/auth/profile",
            headers={"Authorization": f"Bearer {token}"},
            json={bad_field: "HackedValue"},
        )
        assert resp.status_code == 422, f"Expected 422 for forbidden field '{bad_field}', got {resp.status_code}"


def test_profile_update_validation_errors(client, seed_users):
    """Blank full_name or invalid phone format returns 422."""
    email = seed_users["recruiter"]["email"]
    token = create_access_token({"sub": email})

    # Blank full_name
    resp1 = client.put(
        "/api/auth/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "   "},
    )
    assert resp1.status_code == 422

    # Invalid phone
    resp2 = client.put(
        "/api/auth/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"phone_number": "not-a-number"},
    )
    assert resp2.status_code == 422


def test_password_change_flow(client, seed_users):
    """Password change validates current password and updates hash."""
    email = seed_users["admin"]["email"]
    token = create_access_token({"sub": email})

    # 1. Wrong current password -> 400
    resp_wrong = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "WrongPassword123!",
            "new_password": "BrandNewAdminPass123!",
            "confirm_password": "BrandNewAdminPass123!",
        },
    )
    assert resp_wrong.status_code == 400
    assert "Current password is incorrect" in resp_wrong.json()["detail"]

    # 2. Mismatched confirm password -> 422
    resp_mismatch = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": seed_users["admin"]["password"],
            "new_password": "BrandNewAdminPass123!",
            "confirm_password": "DifferentPassword123!",
        },
    )
    assert resp_mismatch.status_code == 422

    # 3. Too short new password -> 422
    resp_short = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": seed_users["admin"]["password"],
            "new_password": "short",
            "confirm_password": "short",
        },
    )
    assert resp_short.status_code == 422

    # 4. Successful change
    new_pwd = "BrandNewAdminPass123!"
    resp_success = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": seed_users["admin"]["password"],
            "new_password": new_pwd,
            "confirm_password": new_pwd,
        },
    )
    assert resp_success.status_code == 200
    assert "Password changed successfully" in resp_success.json()["message"]

    # 5. Old password no longer works
    old_login = client.post(
        "/api/auth/login",
        json={"email": email, "password": seed_users["admin"]["password"], "role": "Admin"},
    )
    assert old_login.status_code == 401

    # 6. New password works
    new_login = client.post(
        "/api/auth/login",
        json={"email": email, "password": new_pwd, "role": "Admin"},
    )
    assert new_login.status_code == 200

    # Reset back to original password for other tests
    client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": new_pwd,
            "new_password": seed_users["admin"]["password"],
            "confirm_password": seed_users["admin"]["password"],
        },
    )


# ===========================================================================
# Phase 3: Registration and Provisioning Hardening Tests
# ===========================================================================

def test_public_registration_cannot_create_privileged_roles(client):
    """Public registration endpoint strictly forbids creating Recruiter or Admin."""
    for role in ["Recruiter", "Admin"]:
        resp = client.post(
            "/api/auth/register",
            json={
                "full_name": "Intruder User",
                "email": f"intruder_{role.lower()}@example.com",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "company_name": "Intruder Corp",
                "job_title": role,
            },
        )
        assert resp.status_code == 403
        assert "must be created by an administrator" in resp.json()["detail"]

    # Variations with incorrect casing or whitespace fail validation (422)
    for bad_role in ["recruiter", "ADMIN", " recruiter "]:
        resp = client.post(
            "/api/auth/register",
            json={
                "full_name": "Intruder User",
                "email": f"intruder_{bad_role.strip().lower()}@example.com",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "company_name": "Intruder Corp",
                "job_title": bad_role,
            },
        )
        assert resp.status_code == 422


def test_admin_provisioning_can_create_recruiter_and_admin(client, seed_users):
    """Admin provisioning creates Recruiter and Admin with temporary password."""
    admin_email = seed_users["admin"]["email"]
    admin_token = create_access_token({"sub": admin_email})

    import time
    ts = int(time.time())
    prov_email = f"provisioned_rec_{ts}@example.com"

    # Provision Recruiter
    resp = client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "full_name": "Provisioned Recruiter",
            "email": prov_email,
            "job_title": "Recruiter",
            "company_name": "TestCorp",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["email"] == prov_email
    assert data["user"]["job_title"] == "Recruiter"
    temp_pwd = data["temp_password"]
    assert len(temp_pwd) >= 12

    # Sign in with provisioned user under role Recruiter
    login_resp = client.post(
        "/api/auth/login",
        json={"email": prov_email, "password": temp_pwd, "role": "Recruiter"},
    )
    assert login_resp.status_code == 200

    # Mismatched role Candidate is rejected
    mismatch_resp = client.post(
        "/api/auth/login",
        json={"email": prov_email, "password": temp_pwd, "role": "Candidate"},
    )
    assert mismatch_resp.status_code == 403


def test_admin_provisioning_rejected_for_recruiter_and_candidate(client, seed_users):
    """Recruiter and Candidate cannot call POST /api/admin/users (403 Forbidden)."""
    for role in ["recruiter", "candidate"]:
        email = seed_users[role]["email"]
        token = create_access_token({"sub": email})
        resp = client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "full_name": "Sneaky User",
                "email": "sneaky@example.com",
                "job_title": "Admin",
            },
        )
        assert resp.status_code == 403
