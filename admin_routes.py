"""
admin_routes.py — Admin Dashboard API Routes for SmartHire AI.

Dedicated administration endpoints protected by require_admin.
Handles platform overview, user management, audit logs, data health,
candidate purging/restoration, job reassignment, recruiter activity,
AI telemetry, settings, and database backups.
"""

import csv
import io
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session

from database import get_db
from models import (
    User,
    Candidate,
    Job,
    Application,
    InterviewSession,
    ResumeAnalysis,
    AuditLog,
    LlmUsage,
    PlatformSetting,
    utc_now,
)
from auth import decode_access_token, hash_password
from services import audit, settings_store
from schemas import (
    UserResponse,
    AdminOverviewResponse,
    DailySignup,
    AdminUserUpdate,
    AdminUserCreate,
    AdminUserCreateResponse,
    AdminPasswordResetResponse,
    AuditLogResponse,
    DataHealthResponse,
    DuplicateEmailGroup,
    CandidateHealthBrief,
    MissingResumeRecord,
    CandidatePurgeRequest,
    CandidatePurgeResponse,
    CandidateResponse,
    AdminJobResponse,
    AdminJobUpdate,
    RecruiterActivityResponse,
    AiUsageResponse,
    DailyAiUsage,
    TopAiUser,
    PlatformSettingsResponse,
    PlatformSettingsUpdate,
)

# ---------------------------------------------------------------------------
# Auth Dependency for Admin Routes
# ---------------------------------------------------------------------------

SUPPORTED_ROLES = {"Candidate", "Recruiter", "Admin"}
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def require_admin(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Dependency verifying that the caller is authenticated and holds the Admin role."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    email: str = payload.get("sub")
    if not email:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise credentials_exception

    if user.job_title not in SUPPORTED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The HR Manager role has been retired and is no longer supported.",
        )

    if str(user.job_title).strip().lower() != "admin":
        audit.log_event(
            db,
            actor=user,
            action="access_denied",
            target_type="role_access",
            details={"user_role": user.job_title, "required_roles": ["Admin"]},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: requires one of ['Admin'] role(s).",
        )

    return user


router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


# ---------------------------------------------------------------------------
# 1. Overview Metrics
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=AdminOverviewResponse)
def get_admin_overview(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Return system-wide overview statistics for platform health and operations."""
    now = utc_now()
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    # User counts by role
    role_counts: Dict[str, int] = {"Candidate": 0, "Recruiter": 0, "Admin": 0}
    role_groups = db.query(User.job_title, func.count(User.user_id)).group_by(User.job_title).all()
    for role, count in role_groups:
        if role in role_counts:
            role_counts[role] = count
        elif role:
            role_counts[role] = count

    # Active users by last_login_at
    active_7d = db.query(User).filter(User.last_login_at >= cutoff_7d).count()
    active_30d = db.query(User).filter(User.last_login_at >= cutoff_30d).count()

    # Signups per day for last 30 days
    users_30d = db.query(User.created_at).filter(User.created_at >= cutoff_30d).all()
    signup_buckets: Dict[str, int] = {}
    for d in range(29, -1, -1):
        dt_str = (now - timedelta(days=d)).strftime("%Y-%m-%d")
        signup_buckets[dt_str] = 0

    for u_row in users_30d:
        if u_row.created_at:
            dt_str = u_row.created_at.strftime("%Y-%m-%d")
            if dt_str in signup_buckets:
                signup_buckets[dt_str] += 1

    signups_series = [DailySignup(date=k, count=v) for k, v in signup_buckets.items()]

    # Jobs open / closed
    jobs_open = db.query(Job).filter(func.lower(Job.status) == "open").count()
    jobs_closed = db.query(Job).filter(func.lower(Job.status) == "closed").count()

    # Candidate count (excluding soft-deleted)
    candidate_count = db.query(Candidate).filter(Candidate.deleted_at.is_(None)).count()

    # Interviews by status
    interview_groups = (
        db.query(InterviewSession.status, func.count(InterviewSession.session_id))
        .group_by(InterviewSession.status)
        .all()
    )
    interviews_by_status: Dict[str, int] = {
        (status_str or "unknown"): cnt for status_str, cnt in interview_groups
    }

    # Resume analyses
    analyses_count = db.query(ResumeAnalysis).count()

    # AI calls and error rate last 7 days
    ai_records = db.query(LlmUsage).filter(LlmUsage.created_at >= cutoff_7d).all()
    ai_calls_7d = len(ai_records)
    ai_errors_7d = sum(1 for r in ai_records if not r.success)
    ai_error_rate_7d = round((ai_errors_7d / ai_calls_7d * 100.0), 2) if ai_calls_7d > 0 else 0.0

    # DB and Uploads file sizes
    db_size = os.path.getsize("smarthire.db") if os.path.exists("smarthire.db") else 0
    uploads_size = 0
    if os.path.exists("uploads"):
        for root, _, files in os.walk("uploads"):
            for f in files:
                fp = os.path.join(root, f)
                if os.path.isfile(fp):
                    uploads_size += os.path.getsize(fp)

    return AdminOverviewResponse(
        user_counts_by_role=role_counts,
        active_users_7d=active_7d,
        active_users_30d=active_30d,
        signups_per_day_30d=signups_series,
        jobs_open=jobs_open,
        jobs_closed=jobs_closed,
        candidate_count=candidate_count,
        interviews_by_status=interviews_by_status,
        resume_analyses_count=analyses_count,
        ai_calls_7d=ai_calls_7d,
        ai_error_rate_7d=ai_error_rate_7d,
        db_file_size_bytes=db_size,
        uploads_folder_size_bytes=uploads_size,
    )


# ---------------------------------------------------------------------------
# 2. User Management
# ---------------------------------------------------------------------------

@router.get("/users", response_model=List[UserResponse])
def get_admin_users(
    q: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """List users with filtering by query, role, status, with pagination."""
    query = db.query(User)

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(User.full_name.ilike(term), User.email.ilike(term)))

    if role and role.strip():
        query = query.filter(func.lower(User.job_title) == role.strip().lower())

    if status and status.strip():
        st = status.strip().lower()
        if st == "active":
            query = query.filter(User.is_active.is_(True))
        elif st in ("inactive", "disabled"):
            query = query.filter(User.is_active.is_(False))

    query = query.order_by(User.user_id.asc())

    if offset > 0:
        query = query.offset(offset)
    if limit is not None and limit > 0:
        query = query.limit(limit)

    users = query.all()
    return [UserResponse.from_orm_model(u) for u in users]


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user_status_or_role(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Update a user's job_title or is_active status.
    Requires a non-empty reason string.
    Enforces self-protection (cannot deactivate/demote self) and last-active-admin rule.
    """
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(
            status_code=400,
            detail="A non-empty reason string is required for user status or role modifications.",
        )

    target = db.query(User).filter(User.user_id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Rule: An admin cannot change their own role or deactivate themselves
    is_self = target.user_id == admin.user_id
    if is_self:
        demoting_self = payload.job_title is not None and payload.job_title.strip() != target.job_title
        deactivating_self = payload.is_active is False
        if demoting_self or deactivating_self:
            raise HTTPException(
                status_code=400,
                detail="Admins cannot change their own role or deactivate their own account.",
            )

    # Rule: The last active Admin can never be demoted or deactivated
    is_target_active_admin = (target.job_title == "Admin" and target.is_active)
    will_demote = payload.job_title is not None and payload.job_title.strip() != "Admin"
    will_deactivate = payload.is_active is False
    if is_target_active_admin and (will_demote or will_deactivate):
        active_admin_count = (
            db.query(User)
            .filter(User.job_title == "Admin", User.is_active.is_(True))
            .count()
        )
        if active_admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot demote or deactivate the last active Admin.",
            )

    changes: Dict[str, Any] = {}

    if payload.job_title is not None:
        new_role = payload.job_title.strip()
        if new_role not in SUPPORTED_ROLES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role '{new_role}'. Must be one of {list(SUPPORTED_ROLES)}.",
            )
        if new_role != target.job_title:
            changes["job_title"] = {"from": target.job_title, "to": new_role}
            target.job_title = new_role

    if payload.is_active is not None and payload.is_active != target.is_active:
        changes["is_active"] = {"from": target.is_active, "to": payload.is_active}
        target.is_active = payload.is_active

    db.commit()
    db.refresh(target)

    audit.log_event(
        db,
        actor=admin,
        action="update_user",
        target_type="user",
        target_id=str(target.user_id),
        details={"changes": changes, "reason": payload.reason.strip()},
    )

    return UserResponse.from_orm_model(target)


@router.post("/users", response_model=AdminUserCreateResponse, status_code=201)
def create_admin_user(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Create a user with a generated random temporary password returned once."""
    role = payload.job_title.strip()
    if role not in SUPPORTED_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{role}'. Must be one of {list(SUPPORTED_ROLES)}.",
        )

    clean_email = payload.email.strip().lower()
    existing = db.query(User).filter(func.lower(User.email) == clean_email).first()
    if existing:
        raise HTTPException(status_code=400, detail="A user with this email address already exists.")

    temp_password = f"Temp-{secrets.token_urlsafe(8)}@1"

    new_user = User(
        full_name=payload.full_name.strip(),
        email=clean_email,
        password_hash=hash_password(temp_password),
        company_name=(payload.company_name or "SmartHire").strip(),
        job_title=role,
        phone_number=payload.phone_number.strip() if payload.phone_number else None,
        is_active=True,
        created_at=utc_now(),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    audit.log_event(
        db,
        actor=admin,
        action="create_user",
        target_type="user",
        target_id=str(new_user.user_id),
        details={"email": new_user.email, "role": new_user.job_title},
    )

    return AdminUserCreateResponse(
        user=UserResponse.from_orm_model(new_user),
        temp_password=temp_password,
    )


@router.post("/users/{user_id}/reset-password", response_model=AdminPasswordResetResponse)
def reset_user_password(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Reset an existing user's password with a generated random temporary password returned once."""
    target = db.query(User).filter(User.user_id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    temp_password = f"Reset-{secrets.token_urlsafe(8)}@1"
    target.password_hash = hash_password(temp_password)
    db.commit()

    audit.log_event(
        db,
        actor=admin,
        action="reset_password",
        target_type="user",
        target_id=str(target.user_id),
        details={"email": target.email},
    )

    return AdminPasswordResetResponse(
        user_id=target.user_id,
        email=target.email,
        temp_password=temp_password,
    )


# ---------------------------------------------------------------------------
# 3. Audit Logs
# ---------------------------------------------------------------------------

@router.get("/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    actor_email: Optional[str] = None,
    action: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    format: Optional[str] = None,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Retrieve audit logs with filtering, pagination, and optional CSV export."""
    query = db.query(AuditLog)

    if actor_email and actor_email.strip():
        query = query.filter(func.lower(AuditLog.actor_email) == actor_email.strip().lower())

    if action and action.strip():
        query = query.filter(AuditLog.action == action.strip())

    if date_from:
        query = query.filter(AuditLog.created_at >= date_from)

    if date_to:
        query = query.filter(AuditLog.created_at <= date_to)

    query = query.order_by(AuditLog.audit_id.desc())

    if format and format.strip().lower() == "csv":
        logs = query.offset(offset).limit(limit).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "audit_id",
            "created_at",
            "actor_id",
            "actor_email",
            "action",
            "target_type",
            "target_id",
            "details",
        ])
        for row in logs:
            writer.writerow([
                row.audit_id,
                row.created_at.isoformat() if row.created_at else "",
                row.actor_id or "",
                row.actor_email or "",
                row.action or "",
                row.target_type or "",
                row.target_id or "",
                row.details or "",
            ])
        csv_data = output.getvalue()
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
        )

    logs = query.offset(offset).limit(limit).all()
    return [AuditLogResponse.model_validate(l) for l in logs]


# ---------------------------------------------------------------------------
# 4. Data Health & Diagnostics
# ---------------------------------------------------------------------------

@router.get("/data-health", response_model=DataHealthResponse)
def get_data_health(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Inspect data health: duplicate candidates, empty skills, unreferenced files, missing files."""
    active_candidates = (
        db.query(Candidate)
        .filter(Candidate.deleted_at.is_(None))
        .all()
    )

    # 1. Duplicate candidates by lowercase email
    email_groups: Dict[str, List[int]] = {}
    for c in active_candidates:
        if c.email and c.email.strip():
            clean = c.email.strip().lower()
            email_groups.setdefault(clean, []).append(c.candidate_id)

    duplicates: List[DuplicateEmailGroup] = [
        DuplicateEmailGroup(email=email, count=len(ids), candidate_ids=ids)
        for email, ids in email_groups.items()
        if len(ids) > 1
    ]

    # 2. Candidates with empty skills
    empty_skills: List[CandidateHealthBrief] = []
    for c in active_candidates:
        skills_str = (c.skills or "").strip()
        if not skills_str or skills_str == "[]":
            empty_skills.append(CandidateHealthBrief(candidate_id=c.candidate_id, name=c.name, email=c.email))
        else:
            try:
                parsed = json.loads(skills_str)
                if not parsed:
                    empty_skills.append(CandidateHealthBrief(candidate_id=c.candidate_id, name=c.name, email=c.email))
            except Exception:
                empty_skills.append(CandidateHealthBrief(candidate_id=c.candidate_id, name=c.name, email=c.email))

    # 3. Resume file cross-checks
    active_paths: set = set()
    missing_files: List[MissingResumeRecord] = []
    for c in active_candidates:
        if c.resume_path and c.resume_path.strip():
            raw_path = c.resume_path.strip()
            if raw_path.startswith("dataset_row_"):
                continue
            fname = os.path.basename(raw_path)
            active_paths.add(fname)
            # Check existence both as absolute/relative path and inside uploads/
            exists = os.path.exists(raw_path) or os.path.exists(os.path.join("uploads", fname))
            if not exists:
                missing_files.append(MissingResumeRecord(
                    candidate_id=c.candidate_id,
                    name=c.name,
                    resume_path=raw_path,
                ))

    unreferenced_files: List[str] = []
    if os.path.exists("uploads"):
        for f in os.listdir("uploads"):
            if f.startswith("."):
                continue
            full_p = os.path.join("uploads", f)
            if os.path.isfile(full_p):
                if f not in active_paths:
                    unreferenced_files.append(f)

    return DataHealthResponse(
        duplicate_candidates=duplicates,
        empty_skills_candidates=empty_skills,
        unreferenced_upload_files=sorted(unreferenced_files),
        missing_resume_files=missing_files,
    )


# ---------------------------------------------------------------------------
# 5. Candidate Purge & Restore
# ---------------------------------------------------------------------------

@router.post("/candidates/purge", response_model=CandidatePurgeResponse)
def purge_candidates(
    payload: CandidatePurgeRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Soft-delete candidates matching criteria (older_than_days, stage).
    Requires confirm_text == f"PURGE {n} RECORDS" where n is matched records.
    """
    query = db.query(Candidate).filter(Candidate.deleted_at.is_(None))

    if payload.older_than_days is not None and payload.older_than_days > 0:
        cutoff = utc_now() - timedelta(days=payload.older_than_days)
        query = query.filter(Candidate.created_at <= cutoff)

    if payload.stage and payload.stage.strip():
        query = query.filter(func.lower(Candidate.stage) == payload.stage.strip().lower())

    matched_candidates = query.all()
    n = len(matched_candidates)
    expected_confirm = f"PURGE {n} RECORDS"

    provided_confirm = (payload.confirm_text or "").strip()
    if provided_confirm != expected_confirm:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Confirmation mismatch. Expected '{expected_confirm}'.",
                "matched_count": n,
                "expected_confirm": expected_confirm,
            },
        )

    now = utc_now()
    for c in matched_candidates:
        c.deleted_at = now
    db.commit()

    audit.log_event(
        db,
        actor=admin,
        action="purge_candidates",
        target_type="candidate",
        details={
            "purged_count": n,
            "older_than_days": payload.older_than_days,
            "stage": payload.stage,
        },
    )

    return CandidatePurgeResponse(
        purged_count=n,
        message=f"Successfully soft-deleted {n} candidate records.",
    )


@router.post("/candidates/{candidate_id}/restore", response_model=CandidateResponse)
def restore_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Restore a previously soft-deleted candidate record."""
    candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate.deleted_at = None

    # Self-healing: recreate pipeline Application if none exists
    existing_app = db.query(Application).filter(Application.candidate_id == candidate.candidate_id).first()
    if not existing_app:
        candidate.stage = "new"
        now_utc = datetime.now(timezone.utc)
        restored_app = Application(
            candidate_id=candidate.candidate_id,
            stage="new",
            stage_history=json.dumps([{
                "from_stage": None,
                "to_stage": "new",
                "timestamp": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "updated_by": admin.email,
                "notes": "Restored by administrator",
            }]),
            created_at=now_utc,
            updated_at=now_utc,
        )
        db.add(restored_app)

    db.commit()
    db.refresh(candidate)

    audit.log_event(
        db,
        actor=admin,
        action="restore_candidate",
        target_type="candidate",
        target_id=str(candidate_id),
    )

    return CandidateResponse.from_orm_model(candidate)


# ---------------------------------------------------------------------------
# 6. Job Governance
# ---------------------------------------------------------------------------

@router.get("/jobs", response_model=List[AdminJobResponse])
def get_admin_jobs(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """List all jobs with owner name and email for administrative oversight."""
    jobs = db.query(Job).order_by(Job.job_id.desc()).all()
    user_ids = {j.created_by for j in jobs if j.created_by}
    users_map = (
        {u.user_id: u for u in db.query(User).filter(User.user_id.in_(user_ids)).all()}
        if user_ids
        else {}
    )

    results: List[AdminJobResponse] = []
    for j in jobs:
        owner = users_map.get(j.created_by)
        results.append(AdminJobResponse(
            job_id=j.job_id,
            title=j.title,
            department=j.department,
            location=j.location,
            status=j.status,
            created_by=j.created_by,
            owner_name=owner.full_name if owner else None,
            owner_email=owner.email if owner else None,
            created_at=j.created_at,
            updated_at=getattr(j, "updated_at", None),
        ))
    return results


@router.patch("/jobs/{job_id}", response_model=AdminJobResponse)
def update_admin_job(
    job_id: int,
    payload: AdminJobUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Reassign job owner or update job status."""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    changes: Dict[str, Any] = {}

    if payload.created_by is not None:
        target_user = db.query(User).filter(User.user_id == payload.created_by).first()
        if not target_user:
            raise HTTPException(status_code=400, detail="Target user for job assignment does not exist")
        changes["created_by"] = {"from": job.created_by, "to": payload.created_by}
        job.created_by = payload.created_by

    if payload.status is not None and payload.status.strip():
        new_status = payload.status.strip().lower()
        changes["status"] = {"from": job.status, "to": new_status}
        job.status = new_status

    db.commit()
    db.refresh(job)

    audit.log_event(
        db,
        actor=admin,
        action="update_job",
        target_type="job",
        target_id=str(job_id),
        details={"changes": changes},
    )

    owner = db.query(User).filter(User.user_id == job.created_by).first() if job.created_by else None
    return AdminJobResponse(
        job_id=job.job_id,
        title=job.title,
        department=job.department,
        location=job.location,
        status=job.status,
        created_by=job.created_by,
        owner_name=owner.full_name if owner else None,
        owner_email=owner.email if owner else None,
        created_at=job.created_at,
        updated_at=getattr(job, "updated_at", None),
    )


# ---------------------------------------------------------------------------
# 7. Recruiter Activity
# ---------------------------------------------------------------------------

@router.get("/recruiters/activity", response_model=List[RecruiterActivityResponse])
def get_recruiters_activity(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Retrieve activity metrics per recruiter (jobs, interviews, uploads, last login)."""
    recruiters = (
        db.query(User)
        .filter(func.lower(User.job_title) == "recruiter")
        .order_by(User.full_name.asc())
        .all()
    )

    results: List[RecruiterActivityResponse] = []
    for r in recruiters:
        jobs_count = db.query(Job).filter(Job.created_by == r.user_id).count()
        interviews_count = db.query(InterviewSession).filter(InterviewSession.created_by == r.user_id).count()
        candidates_count = (
            db.query(func.count(func.distinct(Application.candidate_id)))
            .filter(Application.recruiter_id == r.user_id)
            .scalar()
            or 0
        )

        results.append(RecruiterActivityResponse(
            user_id=r.user_id,
            full_name=r.full_name,
            email=r.email,
            last_login_at=r.last_login_at,
            jobs_created=jobs_count,
            interviews_created=interviews_count,
            candidates_uploaded=candidates_count,
        ))
    return results


# ---------------------------------------------------------------------------
# 8. AI Usage & Telemetry
# ---------------------------------------------------------------------------

@router.get("/ai-usage", response_model=AiUsageResponse)
def get_ai_usage(
    days: int = Query(default=7, ge=1, le=365),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Retrieve AI model usage telemetry, percentiles, error rates, top users, daily series."""
    cutoff = utc_now() - timedelta(days=days)
    records = db.query(LlmUsage).filter(LlmUsage.created_at >= cutoff).all()
    total_calls = len(records)

    calls_per_feature: Dict[str, int] = {}
    latencies: List[int] = []
    errors_count = 0
    user_call_counts: Dict[int, int] = {}
    daily_buckets: Dict[str, Dict[str, Any]] = {}

    now = utc_now()
    for d in range(days - 1, -1, -1):
        dt_str = (now - timedelta(days=d)).strftime("%Y-%m-%d")
        daily_buckets[dt_str] = {"calls": 0, "errors": 0, "latencies": []}

    for r in records:
        feat = r.feature or "unknown"
        calls_per_feature[feat] = calls_per_feature.get(feat, 0) + 1
        if r.latency_ms is not None:
            latencies.append(r.latency_ms)
        if not r.success:
            errors_count += 1
        if r.user_id is not None:
            user_call_counts[r.user_id] = user_call_counts.get(r.user_id, 0) + 1

        day_key = r.created_at.strftime("%Y-%m-%d") if r.created_at else ""
        if day_key in daily_buckets:
            daily_buckets[day_key]["calls"] += 1
            if not r.success:
                daily_buckets[day_key]["errors"] += 1
            if r.latency_ms is not None:
                daily_buckets[day_key]["latencies"].append(r.latency_ms)

    latencies.sort()
    p50 = 0.0
    p95 = 0.0
    if latencies:
        p50_idx = int(0.50 * len(latencies))
        p95_idx = min(int(0.95 * len(latencies)), len(latencies) - 1)
        p50 = float(latencies[p50_idx])
        p95 = float(latencies[p95_idx])

    error_rate = round((errors_count / total_calls * 100.0), 2) if total_calls > 0 else 0.0

    sorted_users = sorted(user_call_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    uids = [u[0] for u in sorted_users]
    user_rows = (
        {u.user_id: u.email for u in db.query(User).filter(User.user_id.in_(uids)).all()}
        if uids
        else {}
    )
    top_10 = [
        TopAiUser(user_id=uid, email=user_rows.get(uid), calls=cnt)
        for uid, cnt in sorted_users
    ]

    daily_series: List[DailyAiUsage] = []
    for dt_str, data in daily_buckets.items():
        avg_lat = (
            round(sum(data["latencies"]) / len(data["latencies"]), 1)
            if data["latencies"]
            else 0.0
        )
        daily_series.append(DailyAiUsage(
            date=dt_str,
            calls=data["calls"],
            errors=data["errors"],
            avg_latency_ms=avg_lat,
        ))

    return AiUsageResponse(
        days=days,
        total_calls=total_calls,
        calls_per_feature=calls_per_feature,
        p50_latency_ms=p50,
        p95_latency_ms=p95,
        error_rate=error_rate,
        top_10_users=top_10,
        daily_series=daily_series,
    )


# ---------------------------------------------------------------------------
# 9. Platform Settings & Backup
# ---------------------------------------------------------------------------

@router.get("/settings", response_model=PlatformSettingsResponse)
def get_admin_settings(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Retrieve platform configuration and feature toggle settings."""
    current = {}
    for k in settings_store.DEFAULT_SETTINGS:
        current[k] = settings_store.get_setting(db, k)
    return PlatformSettingsResponse(settings=current)


@router.put("/settings", response_model=PlatformSettingsResponse)
def update_admin_settings(
    payload: PlatformSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update platform configuration and feature toggles (only known keys allowed)."""
    unknown_keys = [k for k in payload.settings if k not in settings_store.DEFAULT_SETTINGS]
    if unknown_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown setting key(s): {unknown_keys}. Allowed keys: {list(settings_store.DEFAULT_SETTINGS.keys())}",
        )

    for k, v in payload.settings.items():
        settings_store.set_setting(db, k, v, actor=admin)

    audit.log_event(
        db,
        actor=admin,
        action="update_settings",
        target_type="settings",
        details={"updated_keys": list(payload.settings.keys())},
    )

    current = {}
    for k in settings_store.DEFAULT_SETTINGS:
        current[k] = settings_store.get_setting(db, k)
    return PlatformSettingsResponse(settings=current)


@router.get("/backup")
def backup_database(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Download database backup and write an audit log row."""
    db_path = "smarthire.db"
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database file not found")

    audit.log_event(
        db,
        actor=admin,
        action="backup_database",
        target_type="database",
        details={"filename": db_path},
    )

    return FileResponse(
        path=db_path,
        filename="smarthire_backup.db",
        media_type="application/octet-stream",
    )
