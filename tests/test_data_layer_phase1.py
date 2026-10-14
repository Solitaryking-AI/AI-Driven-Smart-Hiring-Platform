import pytest
from fastapi.testclient import TestClient
from api import app
from database import SessionLocal
from models import User, Candidate, AuditLog, LlmUsage, PlatformSetting
from services import audit, settings_store
from services.llm_client import call_llm
from auth import create_access_token, hash_password
from datetime import datetime, timezone
import uuid

client = TestClient(app)


def test_audit_log_service():
    db = SessionLocal()
    try:
        # 1. Successful log with User instance
        user = User(
            full_name="Audit Tester",
            email=f"audit_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="fakehash",
            company_name="Test",
            job_title="Candidate",
        )
        db.add(user)
        db.commit()

        entry = audit.log_event(
            db,
            actor=user,
            action="test_action",
            target_type="system",
            target_id="123",
            details={"key": "value"},
        )
        assert entry is not None
        assert entry.action == "test_action"
        assert entry.actor_id == user.user_id
        assert entry.actor_email == user.email
        assert entry.target_type == "system"
        assert entry.target_id == "123"
        assert '"key": "value"' in entry.details

        # 2. Never raises on invalid/failing DB calls
        class FailingDb:
            def add(self, obj):
                raise RuntimeError("DB Connection Dropped")
            def rollback(self):
                pass
        
        result = audit.log_event(FailingDb(), actor="nobody@example.com", action="fail_action")
        assert result is None  # Handled safely, did not raise
    finally:
        db.close()


def test_settings_store_service():
    db = SessionLocal()
    try:
        # Default fallback
        reg_open = settings_store.get_setting(db, "registration_open")
        assert reg_open == "true"

        custom_def = settings_store.get_setting(db, "non_existent_key", default="custom_val")
        assert custom_def == "custom_val"

        # Set setting
        setting_row = settings_store.set_setting(db, "maintenance_banner", "Scheduled downtime at 2 AM", actor="admin@smarthire.local")
        assert setting_row.key == "maintenance_banner"
        assert setting_row.value == "Scheduled downtime at 2 AM"
        assert setting_row.updated_by == "admin@smarthire.local"

        read_back = settings_store.get_setting(db, "maintenance_banner")
        assert read_back == "Scheduled downtime at 2 AM"
    finally:
        db.close()


def test_login_and_register_audit_logging_and_last_login_at():
    db = SessionLocal()
    try:
        cand_email = f"logtest_{uuid.uuid4().hex[:6]}@example.com"
        
        # 1. Register candidate
        reg_res = client.post("/api/auth/register", json={
            "full_name": "Login Log Tester",
            "email": cand_email,
            "password": "Password123!",
            "confirm_password": "Password123!",
            "company_name": "Candidate",
            "job_title": "Candidate"
        })
        assert reg_res.status_code == 201

        # Check register_success audit log
        reg_audit = db.query(AuditLog).filter(
            AuditLog.actor_email == cand_email,
            AuditLog.action == "register_success"
        ).first()
        assert reg_audit is not None

        # Check user last_login_at
        user_row = db.query(User).filter(User.email == cand_email).first()
        assert user_row is not None
        assert user_row.last_login_at is not None

        # 2. Failed login (wrong password)
        bad_login = client.post("/api/auth/login", json={
            "email": cand_email,
            "password": "WrongPassword!"
        })
        assert bad_login.status_code == 401

        bad_audit = db.query(AuditLog).filter(
            AuditLog.action == "login_failure"
        ).order_by(AuditLog.audit_id.desc()).first()
        assert bad_audit is not None
        assert "invalid_credentials" in (bad_audit.details or "")

        # 3. Successful login
        t_before = user_row.last_login_at
        good_login = client.post("/api/auth/login", json={
            "email": cand_email,
            "password": "Password123!"
        })
        assert good_login.status_code == 200

        db.refresh(user_row)
        assert user_row.last_login_at is not None

        login_audit = db.query(AuditLog).filter(
            AuditLog.actor_email == cand_email,
            AuditLog.action == "login_success"
        ).first()
        assert login_audit is not None
    finally:
        db.close()


def test_candidate_soft_delete_and_listing_exclusion():
    db = SessionLocal()
    rec_email = f"rec_soft_{uuid.uuid4().hex[:6]}@example.com"
    rec_user = User(
        full_name="Soft Delete Recruiter",
        email=rec_email,
        password_hash=hash_password("Password123!"),
        company_name="SmartHire",
        job_title="Recruiter"
    )
    db.add(rec_user)

    cand = Candidate(
        name="Soft Delete Cand",
        email=f"cand_soft_{uuid.uuid4().hex[:6]}@example.com",
        skills='["Python", "FastAPI"]',
        stage="new"
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    cand_id = cand.candidate_id

    rec_token = create_access_token({"sub": rec_email})
    headers = {"Authorization": f"Bearer {rec_token}"}

    try:
        # Candidate visible before deletion
        get_res = client.get(f"/api/candidates/{cand_id}", headers=headers)
        assert get_res.status_code == 200

        # Perform soft delete
        del_res = client.delete(f"/api/candidates/{cand_id}", headers=headers)
        assert del_res.status_code == 200

        # Verify candidate row still in DB but deleted_at is set
        db.refresh(cand)
        assert cand.deleted_at is not None

        # Excluded from GET /api/candidates/{id} -> 404
        get_after = client.get(f"/api/candidates/{cand_id}", headers=headers)
        assert get_after.status_code == 404

        # Excluded from candidate listing
        list_res = client.get(f"/api/candidates?search={cand.name}", headers=headers)
        assert list_res.status_code == 200
        found_ids = [c["candidate_id"] for c in list_res.json()["candidates"]]
        assert cand_id not in found_ids

        # Check audit log written for deletion
        del_audit = db.query(AuditLog).filter(
            AuditLog.action == "delete_candidate",
            AuditLog.target_id == str(cand_id),
            AuditLog.actor_email == rec_email
        ).order_by(AuditLog.audit_id.desc()).first()
        assert del_audit is not None
        assert del_audit.actor_email == rec_email
    finally:
        cleanup_db = SessionLocal()
        try:
            cleanup_db.query(AuditLog).filter(AuditLog.actor_email == rec_email).delete()
            c = cleanup_db.query(Candidate).filter(Candidate.candidate_id == cand_id).first()
            if c:
                cleanup_db.delete(c)
            u = cleanup_db.query(User).filter(User.email == rec_email).first()
            if u:
                cleanup_db.delete(u)
            cleanup_db.commit()
        finally:
            cleanup_db.close()
        db.close()


def test_llm_usage_telemetry_recording():
    db = SessionLocal()
    try:
        # Call LLM with dummy/mock or real call; even if it fails due to no key or network,
        # LlmUsage record must be created and failure must not break the call unexpectedly.
        try:
            call_llm(
                system_prompt="You are a test assistant.",
                messages=[{"role": "user", "content": "Ping"}],
                feature="resume_summary",
                user_id=42
            )
        except Exception:
            pass  # If API key is missing or invalid, an exception is raised by call_llm, but LlmUsage was still logged!

        usage_row = db.query(LlmUsage).order_by(LlmUsage.usage_id.desc()).first()
        assert usage_row is not None
        assert usage_row.feature == "resume_summary"
        assert usage_row.user_id == 42
        assert usage_row.input_chars > 0
    finally:
        db.close()
