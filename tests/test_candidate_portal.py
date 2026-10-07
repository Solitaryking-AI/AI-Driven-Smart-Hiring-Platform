"""
tests/test_candidate_portal.py — SmartHire AI Candidate Portal Tests
Validates:
  1. Candidate registration & authentication
  2. Candidate profile management & editing
  3. Resume upload & parsing
  4. AI Resume intelligence & ATS feedback
  5. Practice questions & answer evaluation
  6. AI Mock interview session lifecycle & evaluation report
  7. Candidate data isolation
"""

import io
import pytest
from fastapi.testclient import TestClient
from api import app
from database import get_db, SessionLocal
from models import User, Job, Candidate, InterviewSession, ResumeAnalysis, PracticeAnswer

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_test_users():
    db = SessionLocal()
    test_emails = [
        "candidate_test_1@example.com",
        "candidate_profile_test@example.com",
        "candidate_upload_test@example.com",
        "candidate_analysis_test@example.com",
        "candidate_practice_test@example.com",
        "candidate_interview_test@example.com",
        "c1_isolation@example.com",
        "c2_isolation@example.com",
    ]
    user_ids = [u.user_id for u in db.query(User).filter(User.email.in_(test_emails)).all()]
    if user_ids:
        db.query(InterviewSession).filter(InterviewSession.created_by.in_(user_ids)).delete(synchronize_session=False)
        db.query(PracticeAnswer).filter(PracticeAnswer.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(ResumeAnalysis).filter(ResumeAnalysis.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(Candidate).filter(Candidate.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()
    db.close()
    yield
    # Also clean up after test run
    db = SessionLocal()
    user_ids = [u.user_id for u in db.query(User).filter(User.email.in_(test_emails)).all()]
    if user_ids:
        db.query(InterviewSession).filter(InterviewSession.created_by.in_(user_ids)).delete(synchronize_session=False)
        db.query(PracticeAnswer).filter(PracticeAnswer.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(ResumeAnalysis).filter(ResumeAnalysis.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(Candidate).filter(Candidate.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()
    db.close()


@pytest.fixture(scope="module")
def setup_data():
    db = SessionLocal()
    # Create a test job
    job = db.query(Job).filter(Job.title == "Test Backend Engineer").first()
    if not job:
        job = Job(
            title="Test Backend Engineer",
            department="Engineering",
            seniority="Mid-Level",
            min_experience_years=2,
            required_skills='["Python", "FastAPI", "SQL", "Docker"]',
            nice_to_have_skills='["AWS", "Redis"]',
            description="Looking for an experienced backend developer proficient in Python and FastAPI.",
            status="open",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
    job_id = job.job_id
    db.close()
    yield {"job_id": job_id}


def test_candidate_registration_and_login():
    email = "candidate_test_1@example.com"
    # Ensure fresh state
    db = SessionLocal()
    db.query(User).filter(User.email == email).delete()
    db.commit()
    db.close()

    # Register candidate
    reg_payload = {
        "full_name": "Test Candidate Alpha",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "job_title": "Candidate",
        "company_name": "",  # should default to Candidate
        "phone_number": "+1234567890",
    }
    res = client.post("/api/auth/register", json=reg_payload)
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["user"]["job_title"] == "Candidate"
    assert data["user"]["company_name"] == "Candidate"

    # Login
    login_payload = {"email": email, "password": "Password123!"}
    res = client.post("/api/auth/login", json=login_payload)
    assert res.status_code == 200
    token = res.json()["access_token"]
    assert token is not None


def test_candidate_profile_management():
    email = "candidate_profile_test@example.com"
    reg_payload = {
        "full_name": "Profile Candidate",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "job_title": "Candidate",
    }
    reg_res = client.post("/api/auth/register", json=reg_payload)
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get profile
    res = client.get("/api/candidate/profile", headers=headers)
    assert res.status_code == 200
    prof = res.json()
    assert prof["email"] == email

    # Update profile
    update_payload = {
        "name": "Updated Profile Candidate",
        "phone": "+9876543210",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "education": [{"raw": "B.S. in Computer Science", "degree": "B.S."}],
        "experience": [{"raw": "Software Engineer at TechCorp (2022-2024)"}],
        "projects": ["Built real-time analytics engine processing 10k events/sec."],
        "certifications": ["AWS Certified Developer"],
    }
    up_res = client.put("/api/candidate/profile", json=update_payload, headers=headers)
    assert up_res.status_code == 200
    updated = up_res.json()
    assert updated["name"] == "Updated Profile Candidate"
    assert "FastAPI" in updated["skills"]
    assert len(updated["projects"]) == 1


def test_candidate_resume_upload():
    email = "candidate_upload_test@example.com"
    reg_payload = {
        "full_name": "Resume Uploader",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "job_title": "Candidate",
    }
    reg_res = client.post("/api/auth/register", json=reg_payload)
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    sample_resume = """
    John Doe
    john.doe@example.com
    +1 555 123 4567

    Education:
    Bachelor of Technology in Computer Science

    Skills:
    Python, SQL, Docker, React, Git, Machine Learning

    Experience:
    Backend Engineer at DataCorp 2021 - 2023
    - Built scalable microservices using Python and Docker.

    Projects:
    - Smart Recommendation Engine: Implemented collaborative filtering in Python.
    """
    files = {"file": ("test_resume.txt", io.BytesIO(sample_resume.encode("utf-8")), "text/plain")}
    res = client.post("/api/candidate/resume/upload", files=files, headers=headers)
    assert res.status_code == 200
    profile = res.json()
    assert profile["resume_path"] == "test_resume.txt"
    assert "Python" in profile["skills"]


def test_candidate_resume_analysis(setup_data):
    job_id = setup_data["job_id"]
    email = "candidate_analysis_test@example.com"
    reg_payload = {
        "full_name": "Analysis Candidate",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "job_title": "Candidate",
    }
    reg_res = client.post("/api/auth/register", json=reg_payload)
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Set up some skills
    client.put(
        "/api/candidate/profile",
        json={"skills": ["Python", "FastAPI", "SQL"], "projects": ["API Service"]},
        headers=headers,
    )

    # Post analysis
    res = client.post("/api/candidate/resume/analyze", json={"target_job_id": job_id}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "analysis" in data
    analysis = data["analysis"]
    assert "executive_summary" in analysis
    assert "ats_feedback" in analysis
    assert "job_alignment" in analysis

    # Get cached analysis
    get_res = client.get(f"/api/candidate/resume/analysis?target_job_id={job_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["analysis_id"] == data["analysis_id"]


def test_candidate_practice_questions_and_answers(setup_data):
    job_id = setup_data["job_id"]
    email = "candidate_practice_test@example.com"
    reg_payload = {
        "full_name": "Practice Candidate",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "job_title": "Candidate",
    }
    reg_res = client.post("/api/auth/register", json=reg_payload)
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Submit practice answer
    submit_payload = {
        "job_id": job_id,
        "question_text": "Explain how you handle database migrations safely in production.",
        "question_type": "Technical",
        "difficulty": "Medium",
        "candidate_answer": (
            "I use Alembic with SQLAlchemy. In production, I always test migrations backwards and forwards "
            "in staging, avoid locking full tables by running column additions as nullable first, and perform "
            "zero-downtime rolling deploys."
        ),
    }
    res = client.post("/api/candidate/practice-answers", json=submit_payload, headers=headers)
    assert res.status_code == 200
    ans_data = res.json()
    assert "feedback" in ans_data
    assert "score" in ans_data["feedback"]
    assert "strengths" in ans_data["feedback"]

    # Retrieve practice history
    hist_res = client.get("/api/candidate/practice-history", headers=headers)
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert len(history) >= 1
    assert history[0]["question_text"] == submit_payload["question_text"]


def test_candidate_mock_interview_lifecycle(setup_data):
    job_id = setup_data["job_id"]
    email = "candidate_interview_test@example.com"
    reg_payload = {
        "full_name": "Interview Candidate",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "job_title": "Candidate",
    }
    reg_res = client.post("/api/auth/register", json=reg_payload)
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Start mock interview
    start_payload = {"job_id": job_id, "interview_type": "mixed", "difficulty": "Medium"}
    start_res = client.post("/api/candidate/mock-interview/start", json=start_payload, headers=headers)
    assert start_res.status_code == 200
    session = start_res.json()
    session_id = session["session_id"]
    assert session["status"] == "in_progress"
    assert len(session["transcript"]) >= 1  # opening question

    # Respond to interview
    respond_payload = {
        "message": (
            "I have 3 years of experience specializing in backend Python services, RESTful API design with "
            "FastAPI, and database query optimization."
        )
    }
    resp_res = client.post(
        f"/api/candidate/mock-interview/{session_id}/respond",
        json=respond_payload,
        headers=headers,
    )
    assert resp_res.status_code == 200
    resp_data = resp_res.json()
    assert len(resp_data["transcript"]) >= 3  # opening, candidate answer, interviewer follow-up

    # Complete interview & get evaluation
    comp_res = client.post(
        f"/api/candidate/mock-interview/{session_id}/complete",
        headers=headers,
    )
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    assert comp_data["status"] == "completed"
    assert comp_data["feedback"] is not None
    assert "overall_score" in comp_data["feedback"]
    assert "competency_scores" in comp_data["feedback"]

    # List candidate interviews
    list_res = client.get("/api/candidate/mock-interviews", headers=headers)
    assert list_res.status_code == 200
    sessions_list = list_res.json()
    assert any(s["session_id"] == session_id for s in sessions_list)


def test_candidate_data_isolation(setup_data):
    job_id = setup_data["job_id"]
    # Candidate 1
    c1_reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "Candidate One",
            "email": "c1_isolation@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "job_title": "Candidate",
        },
    )
    t1 = c1_reg.json()["access_token"]

    # Candidate 2
    c2_reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "Candidate Two",
            "email": "c2_isolation@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "job_title": "Candidate",
        },
    )
    t2 = c2_reg.json()["access_token"]

    # Candidate 1 creates a mock interview
    start_res = client.post(
        "/api/candidate/mock-interview/start",
        json={"job_id": job_id},
        headers={"Authorization": f"Bearer {t1}"},
    )
    c1_session_id = start_res.json()["session_id"]

    # Candidate 2 attempts to access Candidate 1's mock interview -> 403 Forbidden
    unauth_res = client.get(
        f"/api/candidate/mock-interviews/{c1_session_id}",
        headers={"Authorization": f"Bearer {t2}"},
    )
    assert unauth_res.status_code == 403

    # Candidate 2 attempts to respond to Candidate 1's session -> 403 Forbidden
    unauth_post = client.post(
        f"/api/candidate/mock-interview/{c1_session_id}/respond",
        json={"message": "Infiltrating session"},
        headers={"Authorization": f"Bearer {t2}"},
    )
    assert unauth_post.status_code == 403
