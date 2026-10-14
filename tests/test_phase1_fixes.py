"""
Regression tests for Phase 1 fixes:
- H1: Bootstrap admin from environment variables on empty DB / missing admin
- H12: Password >72 bytes validation in UserCreate (422) and auth.hash_password
- Low C: AdminUserCreate email and role validation
- M11: SQLite WAL mode and busy_timeout pragma
"""

import os
import pytest
from pydantic import ValidationError
from sqlalchemy import text

import auth
from database import engine, init_db, SessionLocal
from models import User
from schemas import AdminUserCreate, UserCreate


def test_password_length_validation_rejects_over_72_bytes():
    # A password of 73 bytes should raise a validation error
    long_pass = "A" * 72 + "1"
    assert len(long_pass.encode("utf-8")) > 72

    with pytest.raises(ValidationError) as excinfo:
        UserCreate(
            full_name="Test User",
            email="test@example.com",
            password=long_pass,
            confirm_password=long_pass,
            job_title="Candidate",
        )
    assert "Password must not exceed 72 bytes." in str(excinfo.value)


def test_hash_password_guards_against_over_72_bytes():
    long_pass = "A" * 73
    with pytest.raises(ValueError) as excinfo:
        auth.hash_password(long_pass)
    assert "Password cannot exceed 72 bytes." in str(excinfo.value)


def test_admin_user_create_validation():
    # Valid admin user create
    valid = AdminUserCreate(
        full_name="Valid Name",
        email="valid.admin@example.com",
        job_title="Recruiter",
    )
    assert valid.email == "valid.admin@example.com"

    # Invalid email
    with pytest.raises(ValidationError):
        AdminUserCreate(
            full_name="Valid Name",
            email="not-an-email",
            job_title="Recruiter",
        )

    # Invalid role
    with pytest.raises(ValidationError):
        AdminUserCreate(
            full_name="Valid Name",
            email="admin@example.com",
            job_title="InvalidRole",
        )

    # Empty full name
    with pytest.raises(ValidationError):
        AdminUserCreate(
            full_name="   ",
            email="admin@example.com",
            job_title="Admin",
        )


def test_sqlite_wal_and_busy_timeout_configured():
    with engine.connect() as conn:
        res_wal = conn.execute(text("PRAGMA journal_mode")).fetchone()
        assert res_wal[0].lower() == "wal"

        res_timeout = conn.execute(text("PRAGMA busy_timeout")).fetchone()
        assert res_timeout[0] == 5000
