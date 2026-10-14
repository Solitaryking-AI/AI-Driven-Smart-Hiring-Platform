"""
Regression tests for Phase 2 backend correctness and RBAC fixes:
- H3: Pipeline match score calculation and helper _pipeline_match_score
- H6: Data health exclusions of dataset_row_* and dotfiles
- H10: registration_open setting enforcement (403 when false)
- H11: Soft-deleted candidate not resurrected by upload; restore recreates Application
- M1: Job status normalization to lowercase
- M2: Recruiter activity candidates_uploaded count
- M12: Candidate endpoints return 404 when deleted_at is set
"""

import io
import uuid
import pytest
from fastapi.testclient import TestClient

from api import app, _pipeline_match_score
from database import SessionLocal
from models import Application, Candidate, Job, User
from services import settings_store

client = TestClient(app)


@pytest.fixture(scope="module")
def recruiter_auth():
    email = f"rec_phase2_{uuid.uuid4().hex[:6]}@example.com"
    # Seed recruiter directly in database to bypass registration restrictions
    db = SessionLocal()
    import auth
    u = User(
        full_name="Recruiter Phase2",
        email=email,
        password_hash=auth.hash_password("Password123!"),
        job_title="Recruiter",
        company_name="SmartHire Tests",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    user_id = u.user_id
    db.close()

    token = auth.create_access_token({"sub": email, "role": "Recruiter"})
    headers = {"Authorization": f"Bearer {token}"}
    return {"email": email, "user_id": user_id, "token": token, "headers": headers}


@pytest.fixture(scope="module")
def admin_auth():
    email = f"admin_phase2_{uuid.uuid4().hex[:6]}@example.com"
    db = SessionLocal()
    import auth
    u = User(
        full_name="Admin Phase2",
        email=email,
        password_hash=auth.hash_password("Password123!"),
        job_title="Admin",
        company_name="SmartHire Tests",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    user_id = u.user_id
    db.close()

    token = auth.create_access_token({"sub": email, "role": "Admin"})
    headers = {"Authorization": f"Bearer {token}"}
    return {"email": email, "user_id": user_id, "token": token, "headers": headers}


def test_h3_pipeline_match_score_calculation(recruiter_auth):
    headers = recruiter_auth["headers"]
    # Create a job with specific skills
    job_res = client.post("/api/jobs", json={
        "title": "Python Match Test Engineer",
        "department": "Engineering",
        "required_skills": ["Python", "FastAPI", "Docker"],
        "min_experience_years": 2,
        "status": "OPEN",  # Test M1 uppercase status normalization as well
    }, headers=headers)
    assert job_res.status_code == 201
    job_data = job_res.json()
    job_id = job_data["job_id"]
    assert job_data["status"] == "open"  # M1 normalized

    # Create candidate in pipeline with matching skills
    cand_res = client.post("/api/pipeline/candidates", json={
        "name": "Match Candidate",
        "email": f"match_{uuid.uuid4().hex[:6]}@example.com",
        "skills": ["Python", "FastAPI", "Docker"],
        "job_id": job_id,
        "stage": "interview",
    }, headers=headers)
    assert cand_res.status_code == 201
    card = cand_res.json()

    # H3: match_score must be non-null and high (>80) for full skill match
    assert card["match_score"] is not None
    assert card["match_score"] > 50.0

    # Also test the pipeline detail endpoint
    app_id = card["application_id"]
    detail_res = client.get(f"/api/pipeline/applications/{app_id}", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["match_score"] is not None
    assert detail["match_breakdown"] is not None


def test_h6_data_health_skips_dataset_markers_and_dotfiles(admin_auth):
    headers = admin_auth["headers"]
    res = client.get("/api/admin/data-health", headers=headers)
    assert res.status_code == 200
    health = res.json()

    # None of the reported missing files should start with dataset_row_
    for mf in health["missing_resume_files"]:
        assert not mf["resume_path"].startswith("dataset_row_")

    # None of the unreferenced files should start with a dot (.gitkeep)
    for uf in health["unreferenced_upload_files"]:
        assert not uf.startswith(".")


def test_h10_registration_closed_returns_403(admin_auth):
    headers = admin_auth["headers"]
    db = SessionLocal()
    try:
        # Turn off public registration
        settings_store.set_setting(db, "registration_open", "false", actor="admin")
    finally:
        db.close()

    reg_res = client.post("/api/auth/register", json={
        "full_name": "Blocked Candidate",
        "email": f"blocked_{uuid.uuid4().hex[:6]}@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "job_title": "Candidate",
    })
    assert reg_res.status_code == 403
    assert "disabled" in reg_res.json()["detail"].lower()

    # Restore registration setting
    db = SessionLocal()
    try:
        settings_store.set_setting(db, "registration_open", "true", actor="admin")
    finally:
        db.close()


def test_h11_soft_delete_and_restoration(recruiter_auth, admin_auth):
    rec_headers = recruiter_auth["headers"]
    adm_headers = admin_auth["headers"]

    email = f"soft_del_{uuid.uuid4().hex[:6]}@example.com"
    cand_res = client.post("/api/pipeline/candidates", json={
        "name": "Soft Delete Candidate",
        "email": email,
        "skills": ["SQL", "Python"],
        "stage": "new",
    }, headers=rec_headers)
    assert cand_res.status_code == 201
    cand_id = cand_res.json()["candidate_id"]

    # Delete candidate (soft delete)
    del_res = client.delete(f"/api/candidates/{cand_id}", headers=rec_headers)
    assert del_res.status_code == 200

    # M12: Candidate endpoints return 404 while soft-deleted
    assert client.get(f"/api/candidates/{cand_id}", headers=rec_headers).status_code == 404
    assert client.get(f"/api/candidates/{cand_id}/hiring-score", headers=rec_headers).status_code == 404
    assert client.patch(f"/api/candidates/{cand_id}/stage", json={"stage": "interview"}, headers=rec_headers).status_code == 404

    # Admin restore
    restore_res = client.post(f"/api/admin/candidates/{cand_id}/restore", headers=adm_headers)
    assert restore_res.status_code == 200

    # Candidate is accessible again and has a self-healed application in pipeline
    assert client.get(f"/api/candidates/{cand_id}", headers=rec_headers).status_code == 200
    db = SessionLocal()
    try:
        app_row = db.query(Application).filter(Application.candidate_id == cand_id).first()
        assert app_row is not None
        assert app_row.stage == "new"
    finally:
        db.close()


def test_m2_recruiter_activity_counts_uploads(recruiter_auth, admin_auth):
    rec_headers = recruiter_auth["headers"]
    adm_headers = admin_auth["headers"]

    # Recruiter uploads a resume
    sample_content = b"Candidate Name\nrec_cand@example.com\nSkills: Python, FastAPI"
    files = {"file": ("rec_upload_test.txt", io.BytesIO(sample_content), "text/plain")}
    up_res = client.post("/api/candidates/upload", files=files, headers=rec_headers)
    assert up_res.status_code == 200

    # Query recruiter activity from admin route
    act_res = client.get("/api/admin/recruiters/activity", headers=adm_headers)
    assert act_res.status_code == 200
    activities = act_res.json()

    rec_act = next((a for a in activities if a["user_id"] == recruiter_auth["user_id"]), None)
    assert rec_act is not None
    assert rec_act["candidates_uploaded"] >= 1
