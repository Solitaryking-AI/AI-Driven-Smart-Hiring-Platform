import pytest
from fastapi.testclient import TestClient
from api import app, VALID_PIPELINE_STAGES
from database import SessionLocal
from models import User, Candidate, Job, Application
from auth import create_access_token, hash_password
import uuid
import json

client = TestClient(app)

@pytest.fixture
def auth_tokens():
    # Recruiter
    rec_email = f"rec_pipe_{uuid.uuid4().hex[:6]}@example.com"
    db = SessionLocal()
    rec_user = User(
        full_name="Pipeline Recruiter",
        email=rec_email,
        password_hash=hash_password("Password123!"),
        company_name="SmartHire ATS",
        job_title="Recruiter"
    )
    db.add(rec_user)
    db.commit()
    db.close()
    rec_token = create_access_token({"sub": rec_email})

    # Candidate
    cand_email = f"cand_pipe_{uuid.uuid4().hex[:6]}@example.com"
    c_res = client.post("/api/auth/register", json={
        "full_name": "Pipeline Candidate",
        "email": cand_email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "company_name": "Candidate",
        "job_title": "Candidate"
    })
    cand_token = c_res.json()["access_token"]

    return {"recruiter": rec_token, "candidate": cand_token}


def test_pipeline_all_six_stages_present_and_ordered(auth_tokens):
    headers = {"Authorization": f"Bearer {auth_tokens['recruiter']}"}
    res = client.get("/api/pipeline", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert "stages" in data
    assert "counts" in data
    assert "filtered_counts" in data

    expected_stages = ["new", "shortlisted", "interview", "offered", "hired", "rejected"]
    assert list(data["stages"].keys()) == expected_stages

    # Verify counts match sum of stages
    total_cards = sum(len(cards) for cards in data["stages"].values())
    assert data["counts"]["total"] >= total_cards
    for stg in expected_stages:
        assert stg in data["counts"]
        assert isinstance(data["counts"][stg], int)


def test_pipeline_stage_movement_bidirectional(auth_tokens):
    headers = {"Authorization": f"Bearer {auth_tokens['recruiter']}"}

    # 1. Create a candidate in pipeline
    create_res = client.post("/api/pipeline/candidates", json={
        "name": f"Stage Test User {uuid.uuid4().hex[:4]}",
        "email": f"stage_test_{uuid.uuid4().hex[:6]}@example.com",
        "phone": "+1 555 987 6543",
        "stage": "new",
        "skills": ["Python", "FastAPI"],
        "notes": "Initial candidate note"
    }, headers=headers)
    assert create_res.status_code == 201
    card = create_res.json()
    app_id = card["application_id"]
    assert card["stage"] == "new"

    # 2. Transition through stages: new -> shortlisted -> interview -> offered -> hired -> rejected -> new
    transitions = [
        ("shortlisted", "Strong portfolio"),
        ("interview", "Scheduled technical interview"),
        ("offered", "Offer letter sent"),
        ("hired", "Candidate accepted offer"),
        ("rejected", "Moved back for testing"),
        ("new", "Reset to new stage")
    ]

    for next_stage, note in transitions:
        patch_res = client.patch(
            f"/api/pipeline/applications/{app_id}/stage",
            json={"stage": next_stage, "notes": note},
            headers=headers
        )
        assert patch_res.status_code == 200
        updated_card = patch_res.json()
        assert updated_card["stage"] == next_stage
        assert updated_card["notes"] == note

        # Verify board reflects new column
        board_res = client.get("/api/pipeline", headers=headers)
        assert board_res.status_code == 200
        board = board_res.json()
        stg_card_ids = [c["application_id"] for c in board["stages"][next_stage]]
        assert app_id in stg_card_ids

    # Verify stage history was recorded
    detail_res = client.get(f"/api/pipeline/applications/{app_id}", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["stage_history"]) >= len(transitions)
    latest_hist = detail["stage_history"][-1]
    assert latest_hist["to_stage"] == "new"


def test_pipeline_reject_invalid_stage(auth_tokens):
    headers = {"Authorization": f"Bearer {auth_tokens['recruiter']}"}
    board = client.get("/api/pipeline", headers=headers).json()
    all_cards = [c for cards in board["stages"].values() for c in cards]
    assert len(all_cards) > 0
    test_app_id = all_cards[0]["application_id"]

    # Attempt to move to an invalid stage
    res = client.patch(
        f"/api/pipeline/applications/{test_app_id}/stage",
        json={"stage": "invalid_stage", "notes": "should fail"},
        headers=headers
    )
    assert res.status_code in (400, 422)


def test_hired_and_rejected_candidates_preserved(auth_tokens):
    headers = {"Authorization": f"Bearer {auth_tokens['recruiter']}"}
    create_res = client.post("/api/pipeline/candidates", json={
        "name": "Preserve Candidate",
        "email": f"preserve_{uuid.uuid4().hex[:6]}@example.com",
        "stage": "new"
    }, headers=headers)
    app_id = create_res.json()["application_id"]
    cand_id = create_res.json()["candidate_id"]

    # Move to hired
    client.patch(f"/api/pipeline/applications/{app_id}/stage", json={"stage": "hired"}, headers=headers)
    # Move to rejected
    client.patch(f"/api/pipeline/applications/{app_id}/stage", json={"stage": "rejected"}, headers=headers)

    # Check database: record MUST still exist
    db = SessionLocal()
    try:
        cand = db.query(Candidate).filter(Candidate.candidate_id == cand_id).first()
        app_row = db.query(Application).filter(Application.application_id == app_id).first()
        assert cand is not None, "Candidate must NOT be deleted upon moving to Hired/Rejected"
        assert app_row is not None, "Application must NOT be deleted upon moving to Hired/Rejected"
        assert cand.stage == "rejected"
        assert app_row.stage == "rejected"
    finally:
        db.close()


def test_add_existing_candidate_and_prevent_duplicate(auth_tokens):
    headers = {"Authorization": f"Bearer {auth_tokens['recruiter']}"}
    # Create candidate
    c_res = client.post("/api/pipeline/candidates", json={
        "name": "Duplicate Test Candidate",
        "email": f"dup_cand_{uuid.uuid4().hex[:6]}@example.com",
        "stage": "new"
    }, headers=headers)
    cand_id = c_res.json()["candidate_id"]

    # Create job
    j_res = client.post("/api/jobs", json={
        "title": f"Software Engineer {uuid.uuid4().hex[:4]}",
        "department": "Engineering",
        "required_skills": ["Python", "Docker"]
    }, headers=headers)
    job_id = j_res.json()["job_id"]

    # 1. Add candidate to job
    add_res = client.post("/api/pipeline/applications", json={
        "candidate_id": cand_id,
        "job_id": job_id,
        "stage": "shortlisted",
        "notes": "Matched by recruiter"
    }, headers=headers)
    assert add_res.status_code == 201
    assert add_res.json()["stage"] == "shortlisted"

    # 2. Add duplicate candidate and job -> Must fail with 400
    dup_res = client.post("/api/pipeline/applications", json={
        "candidate_id": cand_id,
        "job_id": job_id,
        "stage": "new"
    }, headers=headers)
    assert dup_res.status_code == 400
    assert "already in the pipeline" in dup_res.json()["detail"].lower()


def test_pipeline_search_and_filtering(auth_tokens):
    headers = {"Authorization": f"Bearer {auth_tokens['recruiter']}"}
    unique_tag = uuid.uuid4().hex[:5]
    c_res = client.post("/api/pipeline/candidates", json={
        "name": f"FilterSpecialCandidate_{unique_tag}",
        "email": f"filterspecial_{unique_tag}@example.com",
        "skills": [f"Skill_{unique_tag}", "React"],
        "stage": "interview"
    }, headers=headers)
    app_id = c_res.json()["application_id"]

    # 1. Search by unique name
    res_search = client.get(f"/api/pipeline?search=FilterSpecialCandidate_{unique_tag}", headers=headers)
    assert res_search.status_code == 200
    s_data = res_search.json()
    assert any(c["application_id"] == app_id for c in s_data["stages"]["interview"])

    # 2. Filter by stage
    res_stage = client.get("/api/pipeline?stage=interview", headers=headers)
    assert res_stage.status_code == 200
    stg_data = res_stage.json()
    assert all(len(stg_data["stages"][s]) == 0 for s in ["new", "shortlisted", "offered", "hired", "rejected"])
    assert any(c["application_id"] == app_id for c in stg_data["stages"]["interview"])

    # Total counts must still reflect total DB counts
    assert stg_data["counts"]["total"] >= 1


def test_pipeline_authorization_guards(auth_tokens):
    rec_headers = {"Authorization": f"Bearer {auth_tokens['recruiter']}"}
    cand_headers = {"Authorization": f"Bearer {auth_tokens['candidate']}"}

    # Recruiter can access pipeline
    r_get = client.get("/api/pipeline", headers=rec_headers)
    assert r_get.status_code == 200

    # Candidate CANNOT access pipeline (403 Forbidden)
    c_get = client.get("/api/pipeline", headers=cand_headers)
    assert c_get.status_code == 403

    # Candidate CANNOT change stages (403 Forbidden)
    c_patch = client.patch("/api/pipeline/applications/1/stage", json={"stage": "hired"}, headers=cand_headers)
    assert c_patch.status_code == 403

    # Candidate CANNOT create pipeline application (403 Forbidden)
    c_post = client.post("/api/pipeline/applications", json={"candidate_id": 1, "stage": "new"}, headers=cand_headers)
    assert c_post.status_code == 403

    # Unauthenticated request (401 Unauthorized)
    unauth = client.get("/api/pipeline")
    assert unauth.status_code == 401
