"""
test_role_isolation.py — Comprehensive Role Isolation Test Suite for SmartHire AI.

Verifies strict separation across Admin, Recruiter, and Candidate roles:
1. Route Matrix Test: Iterates over all FastAPI routes and validates that disallowed
   roles receive HTTP 403 Forbidden, and the allowed role receives a non-401/403 status.
2. Focused security tests: Specific high-value endpoints verifying blocked cross-role access.
3. Code hygiene: Asserts no legacy `_or_admin` string exists anywhere in api.py.
4. Audit trail: Verifies that blocked cross-role attempts trigger an `access_denied` audit log entry.
"""

import os
import re
import pytest
from fastapi.testclient import TestClient

from api import app
from database import SessionLocal
from models import User, AuditLog
from auth import create_access_token, hash_password


@pytest.fixture(scope="module")
def isolation_setup():
    """Create isolated test users and generate access tokens."""
    db = SessionLocal()
    users_data = [
        ("Admin", "iso_admin@test.com", "Admin"),
        ("Recruiter", "iso_recruiter@test.com", "Recruiter"),
        ("Candidate", "iso_candidate@test.com", "Candidate"),
    ]
    tokens = {}
    for name, email, role in users_data:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                full_name=f"Iso {name}",
                email=email,
                password_hash=hash_password("IsoPass123!"),
                company_name="IsoCorp",
                job_title=role,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.job_title = role
            user.is_active = True
            db.commit()
        tokens[role.lower()] = create_access_token({"sub": email})
    db.close()
    return tokens


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def get_all_routes(fastapi_app):
    """Extract all registered routes, unwrapping any mounted APIRouter instances."""
    routes = []
    for r in fastapi_app.routes:
        if hasattr(r, "original_router"):
            for sub in r.original_router.routes:
                routes.append(sub)
        elif hasattr(r, "routes"):
            for sub in r.routes:
                routes.append(sub)
        elif getattr(r, "path", None):
            routes.append(r)
    return routes


def test_route_matrix_role_isolation(client, isolation_setup):
    """
    Route matrix test:
    - Skip /api/auth/*, /docs, /openapi.json, /redoc, static and public setting routes.
    - Classify remaining routes:
      * /api/admin/* -> Admin only
      * /api/candidate/* -> Candidate only
      * All other /api/* -> Recruiter only
    - Call each with all three tokens:
      * Disallowed roles must get 403
      * Allowed role must NOT get 401 or 403 (400, 404, 422 are acceptable)
    """
    tokens = isolation_setup
    all_routes = get_all_routes(app)
    skip_prefixes = ("/api/auth/", "/docs", "/openapi.json", "/redoc", "/api/settings")

    routes_to_test = [
        r for r in all_routes
        if getattr(r, "path", None) and not any(r.path.startswith(p) for p in skip_prefixes)
    ]

    assert len(routes_to_test) >= 60, f"Expected at least 60 active endpoints, found {len(routes_to_test)}"

    for r in routes_to_test:
        methods = [m for m in getattr(r, "methods", ["GET"]) if m not in ("HEAD", "OPTIONS")]
        path = re.sub(r"\{[^}]+\}", "9999", r.path)

        if r.path.startswith("/api/admin/"):
            allowed_role = "admin"
            disallowed_roles = ["recruiter", "candidate"]
        elif r.path.startswith("/api/candidate/"):
            allowed_role = "candidate"
            disallowed_roles = ["admin", "recruiter"]
        else:
            allowed_role = "recruiter"
            disallowed_roles = ["admin", "candidate"]

        for method in methods:
            # 1. Disallowed roles must return 403
            for dis in disallowed_roles:
                headers = {"Authorization": f"Bearer {tokens[dis]}"}
                resp = client.request(method, path, headers=headers, json={})
                assert resp.status_code == 403, (
                    f"Route {method} {r.path} allowed role '{dis}' (got HTTP {resp.status_code}) "
                    f"instead of expected 403 Forbidden"
                )

            # 2. Allowed role must NOT return 401 or 403
            headers_allowed = {"Authorization": f"Bearer {tokens[allowed_role]}"}
            resp_allowed = client.request(method, path, headers=headers_allowed, json={})
            assert resp_allowed.status_code not in (401, 403), (
                f"Route {method} {r.path} blocked allowed role '{allowed_role}' "
                f"with HTTP {resp_allowed.status_code}"
            )


def test_focused_role_isolation(client, isolation_setup):
    """
    Focused security assertions:
    - Admin gets 403 on:
      * GET /api/candidates
      * POST /api/jobs
      * POST /api/match
      * GET /api/analytics/summary
      * interview-session routes
      * /api/candidate/profile
    - Recruiter gets 403 on:
      * GET /api/admin/users
      * GET /api/candidate/profile
    - Candidate gets 403 on:
      * GET /api/admin/users
      * GET /api/candidates
      * POST /api/jobs
      * POST /api/match
      * GET /api/analytics/summary
      * GET /api/interview-sessions
    """
    tokens = isolation_setup
    adm_headers = {"Authorization": f"Bearer {tokens['admin']}"}
    rec_headers = {"Authorization": f"Bearer {tokens['recruiter']}"}
    cand_headers = {"Authorization": f"Bearer {tokens['candidate']}"}

    # Admin blocked endpoints
    assert client.get("/api/candidates", headers=adm_headers).status_code == 403
    assert client.post("/api/jobs", headers=adm_headers, json={"title": "Test"}).status_code == 403
    assert client.post("/api/match", headers=adm_headers, json={}).status_code == 403
    assert client.get("/api/analytics/summary", headers=adm_headers).status_code == 403
    assert client.post("/api/interview-sessions", headers=adm_headers, json={}).status_code == 403
    assert client.get("/api/interview-sessions", headers=adm_headers).status_code == 403
    assert client.get("/api/interview-sessions/9999", headers=adm_headers).status_code == 403
    assert client.post("/api/interview-sessions/9999/respond", headers=adm_headers, json={}).status_code == 403
    assert client.post("/api/interview-sessions/9999/complete", headers=adm_headers, json={}).status_code == 403
    assert client.get("/api/candidate/profile", headers=adm_headers).status_code == 403

    # Recruiter blocked endpoints
    assert client.get("/api/admin/users", headers=rec_headers).status_code == 403
    assert client.get("/api/admin/overview", headers=rec_headers).status_code == 403
    assert client.get("/api/candidate/profile", headers=rec_headers).status_code == 403

    # Candidate blocked endpoints
    assert client.get("/api/admin/users", headers=cand_headers).status_code == 403
    assert client.get("/api/admin/overview", headers=cand_headers).status_code == 403
    assert client.get("/api/candidates", headers=cand_headers).status_code == 403
    assert client.post("/api/jobs", headers=cand_headers, json={"title": "Test"}).status_code == 403
    assert client.post("/api/match", headers=cand_headers, json={}).status_code == 403
    assert client.get("/api/analytics/summary", headers=cand_headers).status_code == 403
    assert client.get("/api/interview-sessions", headers=cand_headers).status_code == 403


def test_no_or_admin_in_api_py():
    """Assert that the deprecated '_or_admin' pattern does not appear in api.py."""
    with open("api.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "_or_admin" not in content, "Found deprecated '_or_admin' role helper in api.py"


def test_access_denied_audit_log_created_for_cross_role_call(client, isolation_setup):
    """Assert that an access_denied audit row is logged when a blocked cross-role call is attempted."""
    tokens = isolation_setup
    adm_headers = {"Authorization": f"Bearer {tokens['admin']}"}
    rec_headers = {"Authorization": f"Bearer {tokens['recruiter']}"}

    db = SessionLocal()
    # 1. Admin attempts Recruiter endpoint
    resp1 = client.get("/api/candidates", headers=adm_headers)
    assert resp1.status_code == 403

    db.expire_all()
    latest_log1 = (
        db.query(AuditLog)
        .filter(AuditLog.action == "access_denied")
        .order_by(AuditLog.audit_id.desc())
        .first()
    )
    assert latest_log1 is not None
    assert latest_log1.action == "access_denied"
    assert latest_log1.target_type == "role_access"
    assert "Admin" in str(latest_log1.details)

    # 2. Recruiter attempts Admin endpoint
    resp2 = client.get("/api/admin/users", headers=rec_headers)
    assert resp2.status_code == 403

    db.expire_all()
    latest_log2 = (
        db.query(AuditLog)
        .filter(AuditLog.action == "access_denied")
        .order_by(AuditLog.audit_id.desc())
        .first()
    )
    assert latest_log2 is not None
    assert latest_log2.action == "access_denied"
    assert latest_log2.target_type == "role_access"
    assert "Recruiter" in str(latest_log2.details)

    db.close()
