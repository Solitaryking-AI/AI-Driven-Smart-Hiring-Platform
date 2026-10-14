"""
tests/test_candidate_dashboard.py — SmartHire AI Candidate Graphical Dashboard Tests.

Validates GET /api/candidate/dashboard-summary:
  1. 401 without token, 403 for Recruiter and Admin roles
  2. New candidate with no data -> 200, valid zero/empty response, no exceptions
  3. Candidate with seeded ResumeAnalysis, PracticeAnswer, and completed InterviewSession ->
     correct aggregates, trend ordering, and caps
  4. Isolation: candidate A's data never appears in candidate B's response
  5. Feature flags reflection (e.g. feature_practice="false")
  6. Malformed JSON in analysis_data, practice feedback, or interview feedback does not cause a 500
"""

import json
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from api import app
from database import SessionLocal
from models import User, Candidate, Job, InterviewSession, ResumeAnalysis, PracticeAnswer, PlatformSetting
from auth import hash_password, create_access_token
from services import settings_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_dash_users():
    """Ensure isolated test users and their related entities are cleaned up."""
    db = SessionLocal()
    test_emails = [
        "dash_cand_a@example.com",
        "dash_cand_b@example.com",
        "dash_cand_new@example.com",
        "dash_cand_malformed@example.com",
        "dash_recruiter@example.com",
        "dash_admin@example.com",
    ]
    users = db.query(User).filter(User.email.in_(test_emails)).all()
    user_ids = [u.user_id for u in users]
    if user_ids:
        cand_ids = [c.candidate_id for c in db.query(Candidate).filter(Candidate.user_id.in_(user_ids)).all()]
        db.query(InterviewSession).filter(
            (InterviewSession.created_by.in_(user_ids)) | (InterviewSession.candidate_id.in_(cand_ids))
        ).delete(synchronize_session=False)
        db.query(PracticeAnswer).filter(PracticeAnswer.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(ResumeAnalysis).filter(ResumeAnalysis.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(Candidate).filter(Candidate.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()
    db.close()
    yield
    # Post-cleanup
    db = SessionLocal()
    users = db.query(User).filter(User.email.in_(test_emails)).all()
    user_ids = [u.user_id for u in users]
    if user_ids:
        cand_ids = [c.candidate_id for c in db.query(Candidate).filter(Candidate.user_id.in_(user_ids)).all()]
        db.query(InterviewSession).filter(
            (InterviewSession.created_by.in_(user_ids)) | (InterviewSession.candidate_id.in_(cand_ids))
        ).delete(synchronize_session=False)
        db.query(PracticeAnswer).filter(PracticeAnswer.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(ResumeAnalysis).filter(ResumeAnalysis.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(Candidate).filter(Candidate.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()
    db.close()


def _create_user(db, email: str, role: str, name: str = "Test User") -> User:
    u = db.query(User).filter(User.email == email).first()
    if not u:
        u = User(
            full_name=name,
            email=email,
            password_hash=hash_password("Password123!"),
            company_name="SmartHire" if role != "Candidate" else "Candidate",
            job_title=role,
            is_active=True,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    return u


def test_dashboard_auth_and_rbac():
    """Endpoint returns 401 for unauthenticated calls and 403 for Recruiter/Admin roles."""
    # 1. No token -> 401
    resp_no_token = client.get("/api/candidate/dashboard-summary")
    assert resp_no_token.status_code == 401

    db = SessionLocal()
    recruiter = _create_user(db, "dash_recruiter@example.com", "Recruiter", "Recruiter Bob")
    admin = _create_user(db, "dash_admin@example.com", "Admin", "Admin Alice")
    rec_email = recruiter.email
    admin_email = admin.email
    db.close()

    # 2. Recruiter token -> 403
    rec_tok = create_access_token({"sub": rec_email})
    resp_rec = client.get(
        "/api/candidate/dashboard-summary",
        headers={"Authorization": f"Bearer {rec_tok}"},
    )
    assert resp_rec.status_code == 403

    # 3. Admin token -> 403
    admin_tok = create_access_token({"sub": admin_email})
    resp_admin = client.get(
        "/api/candidate/dashboard-summary",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert resp_admin.status_code == 403


def test_new_candidate_empty_dashboard():
    """A fresh candidate with no candidate record or activity gets 200 with clean defaults."""
    db = SessionLocal()
    user = _create_user(db, "dash_cand_new@example.com", "Candidate", "Brand New Candidate")
    token = create_access_token({"sub": user.email})
    db.close()

    resp = client.get(
        "/api/candidate/dashboard-summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Profile completeness
    assert "profile_completeness" in data
    assert 0 <= data["profile_completeness"]["score"] <= 100
    assert "Resume Document" in data["profile_completeness"]["missing"]

    # Skills
    assert data["skills"]["total"] == 0
    assert data["skills"]["top_skills"] == []

    # ATS
    assert data["ats"]["latest_score"] is None
    assert data["ats"]["history"] == []
    assert data["ats"]["strengths"] == []
    assert data["ats"]["improvement_areas"] == []

    # Practice
    assert data["practice"]["attempts"] == 0
    assert data["practice"]["avg_score"] is None
    assert data["practice"]["trend"] == []
    assert data["practice"]["by_type"] == {}

    # Mock interviews
    assert data["mock_interviews"]["total"] == 0
    assert data["mock_interviews"]["completed"] == 0
    assert data["mock_interviews"]["avg_overall"] is None
    assert data["mock_interviews"]["latest_competencies"] is None
    assert data["mock_interviews"]["history"] == []

    # Next steps & features
    assert len(data["next_steps"]) > 0
    assert "feature_flags" in data
    assert isinstance(data["feature_flags"]["practice"], bool)


def test_candidate_with_seeded_data_aggregates():
    """Candidate with ATS analyses, practice answers, and mock interviews gets correct statistics."""
    db = SessionLocal()
    user = _create_user(db, "dash_cand_a@example.com", "Candidate", "Candidate Alex")
    token = create_access_token({"sub": user.email})

    # Candidate profile row
    cand = Candidate(
        user_id=user.user_id,
        name=user.full_name,
        email=user.email,
        phone="+1 555 123 4567",
        skills=json.dumps(["Python", "FastAPI", "Docker", "PostgreSQL", "React"]),
        experience=json.dumps([{"role": "Backend Engineer", "company": "TechCorp", "years": 3}]),
        education=json.dumps([{"degree": "B.S. Computer Science", "school": "State Univ"}]),
        projects=json.dumps([{"name": "API Gateway", "desc": "High performance proxy"}]),
        certifications=json.dumps(["AWS Solutions Architect"]),
        resume_path="alex_resume.pdf",
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)

    # Job for mock & fit
    job = Job(
        title="Senior Python Backend Specialist",
        department="Engineering",
        seniority="Senior",
        min_experience_years=3,
        required_skills=json.dumps(["Python", "FastAPI", "Docker"]),
        nice_to_have_skills=json.dumps(["PostgreSQL", "Kubernetes"]),
        description="Build scalable microservices with FastAPI and Docker.",
        status="open",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Seed 2 ResumeAnalyses
    now = datetime.now(timezone.utc)
    a1 = ResumeAnalysis(
        user_id=user.user_id,
        candidate_id=cand.candidate_id,
        analysis_data=json.dumps({
            "ats_feedback": {"ats_score": 75},
            "strengths": ["Clear project impact", "Strong Python fundamentals"],
            "improvement_areas": ["Quantify business metrics", "Add cloud architecture details"],
        }),
        created_at=now,
    )
    a2 = ResumeAnalysis(
        user_id=user.user_id,
        candidate_id=cand.candidate_id,
        analysis_data=json.dumps({
            "ats_feedback": {"ats_score": 88},
            "strengths": ["Excellent ATS formatting", "High keyword density"],
            "improvement_areas": ["Shorten summary paragraph"],
        }),
        created_at=now,
    )
    db.add_all([a1, a2])

    # Seed 3 PracticeAnswers (Technical and Behavioral)
    p1 = PracticeAnswer(
        user_id=user.user_id,
        candidate_id=cand.candidate_id,
        question_text="Explain GIL in Python.",
        question_type="Technical",
        candidate_answer="The Global Interpreter Lock protects Python memory.",
        feedback=json.dumps({"score": 8.0, "verdict": "Strong"}),
        created_at=now,
    )
    p2 = PracticeAnswer(
        user_id=user.user_id,
        candidate_id=cand.candidate_id,
        question_text="Tell me about a challenging bug.",
        question_type="Behavioral",
        candidate_answer="I debugged a race condition using tracing.",
        feedback=json.dumps({"score": 9.0, "verdict": "Exemplary"}),
        created_at=now,
    )
    p3 = PracticeAnswer(
        user_id=user.user_id,
        candidate_id=cand.candidate_id,
        question_text="Design a cache invalidation strategy.",
        question_type="Technical",
        candidate_answer="Use write-through with TTL.",
        feedback=json.dumps({"score": 7.0, "verdict": "Satisfactory"}),
        created_at=now,
    )
    db.add_all([p1, p2, p3])

    # Seed Mock Interview Session (completed)
    s1 = InterviewSession(
        candidate_id=cand.candidate_id,
        job_id=job.job_id,
        status="completed",
        transcript=json.dumps([{"role": "interviewer", "content": "Welcome"}, {"role": "candidate", "content": "Hi"}]),
        feedback=json.dumps({
            "overall_score": 85.0,
            "verdict": "Recommended",
            "competency_scores": {
                "System Design": 80.0,
                "Coding Fundamentals": 90.0,
                "Communication": 85.0,
            },
        }),
        created_by=user.user_id,
        created_at=now,
    )
    db.add(s1)
    db.commit()
    db.close()

    resp = client.get(
        "/api/candidate/dashboard-summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Profile completeness: fully populated -> 100%
    assert data["profile_completeness"]["score"] == 100
    assert len(data["profile_completeness"]["missing"]) == 0
    assert data["profile_completeness"]["breakdown"]["resume_uploaded"] == 100

    # Skills: 5 skills
    assert data["skills"]["total"] == 5
    assert "Python" in data["skills"]["top_skills"]

    # ATS: latest score should be 75 or 88, history length 2
    assert data["ats"]["latest_score"] in (75, 88)
    assert len(data["ats"]["history"]) == 2
    assert len(data["ats"]["strengths"]) > 0

    # Practice: 3 attempts, avg score = (8 + 9 + 7)/3 = 8.0
    assert data["practice"]["attempts"] == 3
    assert data["practice"]["avg_score"] == 8.0
    assert len(data["practice"]["trend"]) == 3
    assert "Technical" in data["practice"]["by_type"]
    assert "Behavioral" in data["practice"]["by_type"]

    # Mock interview: 1 completed, avg = 85.0, competencies populated
    assert data["mock_interviews"]["total"] == 1
    assert data["mock_interviews"]["completed"] == 1
    assert data["mock_interviews"]["avg_overall"] == 85.0
    assert data["mock_interviews"]["latest_competencies"] is not None
    assert "System Design" in data["mock_interviews"]["latest_competencies"]

    # Job fit: up to 6 jobs returned with fit_percent
    assert 1 <= len(data["job_fit"]) <= 6
    for jf in data["job_fit"]:
        assert "fit_percent" in jf
        assert 0.0 <= jf["fit_percent"] <= 100.0
    matched_jobs = [j for j in data["job_fit"] if j["matched"]]
    assert len(matched_jobs) > 0
    assert any("Python" in j["matched"] for j in matched_jobs)

    # Activity: recent events collected
    assert len(data["activity"]) > 0


def test_candidate_data_isolation():
    """Candidate A never sees Candidate B's ATS analyses, practice answers, or mock interviews."""
    db = SessionLocal()
    user_a = _create_user(db, "dash_cand_a@example.com", "Candidate", "Candidate Alice")
    user_b = _create_user(db, "dash_cand_b@example.com", "Candidate", "Candidate Bob")

    tok_a = create_access_token({"sub": user_a.email})
    tok_b = create_access_token({"sub": user_b.email})

    # Add practice answer strictly for user A
    p_a = PracticeAnswer(
        user_id=user_a.user_id,
        question_text="Isolation question for A",
        candidate_answer="Answer A",
        feedback=json.dumps({"score": 9.5}),
    )
    db.add(p_a)
    db.commit()
    db.close()

    # User B requests dashboard summary
    resp_b = client.get(
        "/api/candidate/dashboard-summary",
        headers={"Authorization": f"Bearer {tok_b}"},
    )
    assert resp_b.status_code == 200
    data_b = resp_b.json()

    # User B should have 0 practice attempts and 0 average score
    assert data_b["practice"]["attempts"] == 0
    assert data_b["practice"]["avg_score"] is None
    assert data_b["practice"]["trend"] == []


def test_feature_flags_reflected_in_response():
    """When a feature flag is disabled, it reflects as false in the feature_flags response object."""
    db = SessionLocal()
    user = _create_user(db, "dash_cand_new@example.com", "Candidate", "Feature Flag Test")
    tok = create_access_token({"sub": user.email})

    # Disable feature_practice
    settings_store.set_setting(db, "feature_practice", "false")
    db.commit()
    db.close()

    resp = client.get(
        "/api/candidate/dashboard-summary",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200
    flags = resp.json()["feature_flags"]
    assert flags["practice"] is False

    # Restore flag
    db = SessionLocal()
    settings_store.set_setting(db, "feature_practice", "true")
    db.commit()
    db.close()


def test_malformed_json_graceful_handling():
    """Malformed JSON in database columns does not raise a 500 error."""
    db = SessionLocal()
    user = _create_user(db, "dash_cand_malformed@example.com", "Candidate", "Malformed Cand")
    tok = create_access_token({"sub": user.email})

    # Malformed practice feedback
    p_bad = PracticeAnswer(
        user_id=user.user_id,
        question_text="Malformed feedback test",
        candidate_answer="Answer",
        feedback="{invalid json string...",
    )
    # Malformed resume analysis
    a_bad = ResumeAnalysis(
        user_id=user.user_id,
        analysis_data="NOT_JSON_DATA",
    )
    db.add_all([p_bad, a_bad])
    db.commit()
    db.close()

    resp = client.get(
        "/api/candidate/dashboard-summary",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["practice"]["attempts"] == 1
    assert data["practice"]["avg_score"] is None
