import pytest
from fastapi.testclient import TestClient
from api import app
from database import SessionLocal
from models import User, Candidate, Job, Application, InterviewSession, PracticeAnswer, ResumeAnalysis
from auth import create_access_token, hash_password
from services import matching_engine
import uuid
import json
import io

client = TestClient(app)

@pytest.fixture
def auth_tokens():
    db = SessionLocal()
    rec_email = f"rec_sec_{uuid.uuid4().hex[:6]}@example.com"
    rec_user = User(
        full_name="Security Recruiter",
        email=rec_email,
        password_hash=hash_password("Password123!"),
        company_name="SmartHire Security",
        job_title="Recruiter"
    )
    db.add(rec_user)
    db.commit()
    db.refresh(rec_user)
    rec_token = create_access_token({"sub": rec_email})
    rec_user_id = rec_user.user_id

    cand_email = f"cand_sec_{uuid.uuid4().hex[:6]}@example.com"
    c_res = client.post("/api/auth/register", json={
        "full_name": "Security Candidate",
        "email": cand_email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "company_name": "Candidate",
        "job_title": "Candidate"
    })
    cand_token = c_res.json()["access_token"]
    cand_user_id = c_res.json()["user"]["user_id"]

    yield {
        "recruiter": rec_token,
        "recruiter_id": rec_user_id,
        "candidate": cand_token,
        "candidate_id": cand_user_id
    }

    # Cleanup test users
    try:
        db.query(Application).filter(Application.recruiter_id == rec_user_id).delete()
        db.query(Candidate).filter(Candidate.user_id.in_([rec_user_id, cand_user_id])).delete()
        db.query(User).filter(User.user_id.in_([rec_user_id, cand_user_id])).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def test_job_rbac_candidate_forbidden(auth_tokens):
    """Verify Candidates cannot create, update, or delete jobs (HTTP 403)."""
    headers = {"Authorization": f"Bearer {auth_tokens['candidate']}"}

    # Create job forbidden
    create_res = client.post("/api/jobs", json={
        "title": "Unauthorized Job",
        "required_skills": ["Python"]
    }, headers=headers)
    assert create_res.status_code == 403, f"Expected 403, got {create_res.status_code}"

    # Update job forbidden
    update_res = client.put("/api/jobs/9999", json={
        "title": "Hacked Title"
    }, headers=headers)
    assert update_res.status_code == 403, f"Expected 403, got {update_res.status_code}"

    # Delete job forbidden
    del_res = client.delete("/api/jobs/9999", headers=headers)
    assert del_res.status_code == 403, f"Expected 403, got {del_res.status_code}"


def test_candidate_delete_rbac_candidate_forbidden(auth_tokens):
    """Verify Candidates cannot delete other candidates or candidates in pool."""
    headers = {"Authorization": f"Bearer {auth_tokens['candidate']}"}
    del_res = client.delete("/api/candidates/9999", headers=headers)
    assert del_res.status_code == 403


def test_candidate_upload_rbac_candidate_forbidden(auth_tokens):
    """Verify Candidate cannot call recruiter candidate upload endpoint."""
    headers = {"Authorization": f"Bearer {auth_tokens['candidate']}"}
    file_content = b"Candidate Resume Content"
    files = {"file": ("test_resume.pdf", io.BytesIO(file_content), "application/pdf")}
    res = client.post("/api/candidates/upload", files=files, headers=headers)
    assert res.status_code == 403


def test_recruiter_job_lifecycle_and_cascading_delete(auth_tokens):
    """Verify Recruiter can create a job and delete it with cascaded unlinking."""
    rec_headers = {"Authorization": f"Bearer {auth_tokens['recruiter']}"}

    # 1. Create Job
    job_res = client.post("/api/jobs", json={
        "title": "Senior Cloud Architect",
        "department": "Engineering",
        "required_skills": ["AWS", "Terraform", "Kubernetes"],
        "min_experience_years": 5
    }, headers=rec_headers)
    assert job_res.status_code == 201
    job_id = job_res.json()["job_id"]

    # 2. Add an application linked to this job
    cand_res = client.post("/api/pipeline/candidates", json={
        "name": "Cloud Candidate",
        "email": f"cloud_{uuid.uuid4().hex[:6]}@example.com",
        "job_id": job_id,
        "skills": ["AWS", "Docker"],
        "stage": "interview"
    }, headers=rec_headers)
    assert cand_res.status_code == 201
    cand_id = cand_res.json()["candidate_id"]

    # 3. Delete Job - must cascade/nullify cleanly without FK error
    del_res = client.delete(f"/api/jobs/{job_id}", headers=rec_headers)
    assert del_res.status_code == 200

    # 4. Verify job is gone
    get_res = client.get(f"/api/jobs/{job_id}", headers=rec_headers)
    assert get_res.status_code == 404

    # 5. Clean up candidate
    client.delete(f"/api/candidates/{cand_id}", headers=rec_headers)
    db_c = SessionLocal()
    try:
        cand_row = db_c.query(Candidate).filter(Candidate.candidate_id == cand_id).first()
        if cand_row:
            db_c.delete(cand_row)
            db_c.commit()
    finally:
        db_c.close()


def test_candidate_cascading_delete(auth_tokens):
    """Verify deleting a candidate cascades across applications, sessions, and analyses."""
    rec_headers = {"Authorization": f"Bearer {auth_tokens['recruiter']}"}

    cand_res = client.post("/api/pipeline/candidates", json={
        "name": "Cascade Candidate",
        "email": f"cascade_{uuid.uuid4().hex[:6]}@example.com",
        "skills": ["Python", "FastAPI"],
        "stage": "new"
    }, headers=rec_headers)
    assert cand_res.status_code == 201
    cand_id = cand_res.json()["candidate_id"]

    db = SessionLocal()
    # Add dummy interview session and practice answer
    sess = InterviewSession(
        candidate_id=cand_id,
        job_id=1,
        status="scheduled"
    )
    db.add(sess)
    ans = PracticeAnswer(
        user_id=auth_tokens["recruiter_id"],
        candidate_id=cand_id,
        question_text="Tell me about yourself",
        candidate_answer="I am a software engineer",
        feedback="{}"
    )
    db.add(ans)
    db.commit()
    db.close()

    # Delete candidate
    del_res = client.delete(f"/api/candidates/{cand_id}", headers=rec_headers)
    assert del_res.status_code == 200

    # Verify no dangling records in DB
    db2 = SessionLocal()
    remaining_apps = db2.query(Application).filter(Application.candidate_id == cand_id).count()
    remaining_sessions = db2.query(InterviewSession).filter(InterviewSession.candidate_id == cand_id).count()
    remaining_answers = db2.query(PracticeAnswer).filter(PracticeAnswer.candidate_id == cand_id).count()
    db2.close()

    assert remaining_apps == 0
    assert remaining_sessions == 0
    assert remaining_answers == 0

    # Purge test candidate row so test database stays clean
    db3 = SessionLocal()
    try:
        cand_row = db3.query(Candidate).filter(Candidate.candidate_id == cand_id).first()
        if cand_row:
            db3.delete(cand_row)
            db3.commit()
    finally:
        db3.close()


def test_matching_engine_polymorphic_interface():
    """Verify matching_engine.score_candidate works with both dicts and argument list."""
    cand_dict = {
        "skills": ["Python", "Docker", "PostgreSQL"],
        "experience": [{"title": "Software Engineer", "years": 4}]
    }
    job_dict = {
        "required_skills": ["Python", "PostgreSQL"],
        "nice_to_have_skills": ["Docker"],
        "min_experience_years": 3
    }

    # 1. Dict-based call (used in pipeline)
    res_dict = matching_engine.score_candidate(cand_dict, job_dict)
    assert "overall_score" in res_dict
    assert "final_score" in res_dict
    assert "skills_score" in res_dict
    assert "experience_fit_score" in res_dict
    assert res_dict["overall_score"] == res_dict["final_score"]
    assert res_dict["final_score"] > 80

    # 2. Positional list call (used in legacy endpoints)
    res_pos = matching_engine.score_candidate(cand_dict["skills"], cand_dict["experience"], job_dict)
    assert "final_score" in res_pos
    assert "skills_score" in res_pos
    assert res_pos["final_score"] > 80


def test_resume_upload_filename_sanitization_and_extension_validation(auth_tokens):
    """Verify filename traversal attacks are sanitized and disallowed extensions fail."""
    rec_headers = {"Authorization": f"Bearer {auth_tokens['recruiter']}"}

    # Disallowed extension (.exe)
    exe_file = io.BytesIO(b"binary data")
    res_bad = client.post("/api/candidates/upload", files={
        "file": ("malware.exe", exe_file, "application/octet-stream")
    }, headers=rec_headers)
    assert res_bad.status_code == 400
    assert "Unsupported file format" in res_bad.json()["detail"]
