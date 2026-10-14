import pytest
from fastapi.testclient import TestClient
from api import app, SUPPORTED_ROLES
from database import SessionLocal
from models import User
import auth
from auth import create_access_token, hash_password
import uuid

client = TestClient(app)

def test_supported_roles_constant():
    assert SUPPORTED_ROLES == {"Candidate", "Recruiter", "Admin"}
    assert "HR Manager" not in SUPPORTED_ROLES

def test_registration_allowed_roles():
    # Candidate registration succeeds
    cand_email = f"test_candidate_{uuid.uuid4().hex[:6]}@example.com"
    payload = {
        "full_name": "Test Candidate",
        "email": cand_email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "company_name": "Candidate",
        "job_title": "Candidate",
        "phone_number": "+1234567890"
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201, f"Expected 201 for Candidate, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["user"]["job_title"] == "Candidate"
    assert "access_token" in data

    # Recruiter and Admin registrations are rejected with 403
    for privileged_role in ["Recruiter", "Admin"]:
        priv_email = f"test_{privileged_role.lower()}_{uuid.uuid4().hex[:6]}@example.com"
        priv_payload = {
            "full_name": f"Test {privileged_role}",
            "email": priv_email,
            "password": "Password123!",
            "confirm_password": "Password123!",
            "company_name": "Test Company",
            "job_title": privileged_role,
            "phone_number": "+1234567890"
        }
        priv_res = client.post("/api/auth/register", json=priv_payload)
        assert priv_res.status_code == 403, f"Expected 403 for {privileged_role}, got {priv_res.status_code}: {priv_res.text}"
        detail_msg = str(priv_res.json().get("detail", "")).lower()
        assert "administrator" in detail_msg

def test_registration_rejected_for_hr_manager():
    unique_email = f"test_hr_{uuid.uuid4().hex[:6]}@example.com"
    payload = {
        "full_name": "Test HR Manager",
        "email": unique_email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "company_name": "Test Corp",
        "job_title": "HR Manager",
        "phone_number": "+1234567890"
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code in (400, 422)
    detail_str = str(res.json().get("detail", ""))
    assert "HR Manager" in detail_str or "Candidate, Recruiter, Admin" in detail_str

def test_registration_rejected_for_arbitrary_role():
    unique_email = f"test_arbitrary_{uuid.uuid4().hex[:6]}@example.com"
    payload = {
        "full_name": "Test Arbitrary",
        "email": unique_email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "company_name": "Test Corp",
        "job_title": "SuperUser",
        "phone_number": "+1234567890"
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code in (400, 422)

def test_legacy_hr_manager_login_blocked_with_403():
    # User 1 (jane.test@acme.com) is a legacy HR Manager user
    # First ensure user has a known password hash
    db = SessionLocal()
    try:
        user1 = db.query(User).filter(User.email == "jane.test@acme.com").first()
        if user1:
            user1.password_hash = auth.hash_password("LegacySecret123!")
            db.commit()
    finally:
        db.close()

    # Wrong password gets 401 (preventing role enumeration)
    bad_res = client.post("/api/auth/login", json={
        "email": "jane.test@acme.com",
        "password": "WrongPassword123!"
    })
    assert bad_res.status_code == 401

    # Correct password gets 403 (retired role)
    res = client.post("/api/auth/login", json={
        "email": "jane.test@acme.com",
        "password": "LegacySecret123!"
    })
    assert res.status_code == 403
    assert "HR Manager" in res.json()["detail"]
    assert "retired" in res.json()["detail"].lower()

def test_legacy_hr_manager_token_rejected_at_gateway():
    db = SessionLocal()
    try:
        user1 = db.query(User).filter(User.email == "jane.test@acme.com").first()
        assert user1 is not None, "Legacy HR Manager user record must be preserved in DB"
        assert user1.job_title == "HR Manager"

        # Generate a token for this user using user email in sub
        hr_token = create_access_token({"sub": user1.email, "role": user1.job_title})
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {hr_token}"})
        assert res.status_code == 403
        assert "retired" in res.json()["detail"].lower()
    finally:
        db.close()

def test_role_authorization_levels():
    # 1. Candidate
    cand_email = f"cand_{uuid.uuid4().hex[:6]}@example.com"
    cand_res = client.post("/api/auth/register", json={
        "full_name": "Candidate User",
        "email": cand_email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "company_name": "Candidate",
        "job_title": "Candidate"
    })
    cand_token = cand_res.json()["access_token"]

    # 2. Recruiter
    rec_email = f"rec_{uuid.uuid4().hex[:6]}@example.com"
    db = SessionLocal()
    rec_user = User(
        full_name="Recruiter User",
        email=rec_email,
        password_hash=hash_password("Password123!"),
        company_name="Recruit Corp",
        job_title="Recruiter",
    )
    db.add(rec_user)

    # 3. Admin
    adm_email = f"adm_{uuid.uuid4().hex[:6]}@example.com"
    adm_user = User(
        full_name="Admin User",
        email=adm_email,
        password_hash=hash_password("Password123!"),
        company_name="Admin Corp",
        job_title="Admin",
    )
    db.add(adm_user)
    db.commit()
    db.close()

    rec_token = create_access_token({"sub": rec_email})
    adm_token = create_access_token({"sub": adm_email})

    # Test Candidate permissions:
    # - Cannot access candidate list endpoint (recruiter/admin only)
    cand_fetch_candidates = client.get("/api/candidates", headers={"Authorization": f"Bearer {cand_token}"})
    assert cand_fetch_candidates.status_code == 403

    # - Cannot access admin users endpoint
    cand_fetch_users = client.get("/api/admin/users", headers={"Authorization": f"Bearer {cand_token}"})
    assert cand_fetch_users.status_code == 403

    # - Can access candidate profile
    cand_profile = client.get("/api/candidate/profile", headers={"Authorization": f"Bearer {cand_token}"})
    assert cand_profile.status_code == 200

    # Test Recruiter permissions:
    # - Can access candidate list
    rec_fetch_candidates = client.get("/api/candidates", headers={"Authorization": f"Bearer {rec_token}"})
    assert rec_fetch_candidates.status_code == 200

    # - Cannot access admin users endpoint
    rec_fetch_users = client.get("/api/admin/users", headers={"Authorization": f"Bearer {rec_token}"})
    assert rec_fetch_users.status_code == 403

    # - Cannot perform destructive candidate purge
    rec_purge = client.post("/api/admin/candidates/purge", json={"candidate_ids": [1]}, headers={"Authorization": f"Bearer {rec_token}"})
    assert rec_purge.status_code == 403

    # Test Admin permissions:
    # - Cannot access candidate list (recruiter only)
    adm_fetch_candidates = client.get("/api/candidates", headers={"Authorization": f"Bearer {adm_token}"})
    assert adm_fetch_candidates.status_code == 403

    # - Can access admin users endpoint
    adm_fetch_users = client.get("/api/admin/users", headers={"Authorization": f"Bearer {adm_token}"})
    assert adm_fetch_users.status_code == 200
    user_list = adm_fetch_users.json()
    assert isinstance(user_list, list)
    assert len(user_list) > 0

    # Verify that legacy user records are in the audit list
    emails = [u["email"] for u in user_list]
    assert "jane.test@acme.com" in emails


def test_candidate_forbidden_on_delete_candidate():
    """Verify Candidate token gets 403 on DELETE /api/candidates/{candidate_id}."""
    cand_email = f"cand_del_{uuid.uuid4().hex[:6]}@example.com"
    cand_res = client.post("/api/auth/register", json={
        "full_name": "Delete Tester",
        "email": cand_email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "company_name": "Candidate",
        "job_title": "Candidate"
    })
    assert cand_res.status_code == 201
    cand_token = cand_res.json()["access_token"]

    del_res = client.delete("/api/candidates/9999", headers={"Authorization": f"Bearer {cand_token}"})
    assert del_res.status_code == 403
    assert "forbidden" in del_res.json().get("detail", "").lower() or "requires" in del_res.json().get("detail", "").lower()

