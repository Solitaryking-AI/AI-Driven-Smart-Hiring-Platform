import os
import io
import json
import uvicorn
from collections import Counter
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Literal

import pandas as pd
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from pydantic import BaseModel, ValidationError
from docx import Document

from database import engine, get_db, init_db
from models import (
    Candidate, User, Job, InterviewSession, ResumeAnalysis, PracticeAnswer, Application,
    AuditLog, LlmUsage, PlatformSetting,
)

init_db()
from schemas import (
    CandidateCreate, CandidateResponse, CandidateListResponse,
    SkillFrequency, AnalyticsSummary, MatchResult, MatchBreakdown, HiringScoreBreakdown,
    SkillGapItem, WellCoveredSkill, SkillGapReport, CandidateSkillGap, CandidateDevelopmentReport,
    InterviewQuestionSet, PracticeQuestionSet, InterviewMessage, InterviewSessionResponse, InterviewSessionCreate,
    InterviewCandidateMessage,
    JobCreate, JobUpdate, JobResponse,
    UserCreate, UserLogin, UserResponse, Token, ProfileUpdate, PasswordChange,
    CandidateProfileUpdate, CandidateProfileResponse,
    ResumeAnalysisRequest, ResumeAnalysisResponse,
    PracticeAnswerSubmit, PracticeAnswerResponse,
    CandidateMockInterviewStart,
    VALID_PIPELINE_STAGES, ApplicationStageUpdate, ApplicationNotesUpdate, ApplicationCreate,
    CandidateAddPipeline, ApplicationCardResponse, PipelineBoardResponse, CandidatePipelineDetailResponse,
)
from auth import hash_password, verify_password, create_access_token, decode_access_token
from services import matching_engine, hiring_score, skill_gap_analysis, interview_assistant, candidate_service, audit, settings_store
from skill_taxonomy import format_skill_display
import file_loader
import parser


# ---------------------------------------------------------------------------
# App setup & lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    os.makedirs("uploads", exist_ok=True)
    yield


app = FastAPI(title="SmartHire AI Recruitment Copilot", lifespan=lifespan)

cors_origins_env = os.environ.get("CORS_ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
if not allowed_origins:
    allowed_origins = [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Supported Roles & Auth Dependencies
# ---------------------------------------------------------------------------
SUPPORTED_ROLES = {"Candidate", "Recruiter", "Admin"}
SUPPORTED_ROLES_LOWER = {"candidate", "recruiter", "admin"}


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Decode the Bearer JWT and return the corresponding User row.
    Raises 401 if the token is missing, expired, or invalid.
    Raises 403 if the user's role is retired/unsupported (e.g. HR Manager).
    """
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

    return user


def require_roles(*allowed: str):
    """Dependency factory ensuring current user belongs to one of allowed roles."""
    def role_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        user_role = str(current_user.job_title).strip().lower()
        allowed_normalized = {r.strip().lower() for r in allowed}
        if user_role not in allowed_normalized:
            audit.log_event(
                db,
                actor=current_user,
                action="access_denied",
                target_type="role_access",
                details={"user_role": current_user.job_title, "required_roles": list(allowed)},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of {list(allowed)} role(s).",
            )
        return current_user
    return role_checker


require_admin = require_roles("Admin")
require_recruiter = require_roles("Recruiter")
require_candidate = require_roles("Candidate")


# ---------------------------------------------------------------------------
# Auth endpoints  (public — no authentication required)
# ---------------------------------------------------------------------------

@app.post("/api/auth/register", response_model=Token, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    reg_open = settings_store.get_setting(db, "registration_open", default="true")
    if str(reg_open).lower() == "false":
        audit.log_event(
            db,
            actor=payload.email,
            action="register_failure",
            target_type="user",
            details={"reason": "registration_closed"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public candidate registration is currently disabled by an administrator.",
        )

    role = (payload.job_title or "").strip()
    if role.lower() in ("recruiter", "admin"):
        audit.log_event(
            db,
            actor=payload.email,
            action="register_failure",
            target_type="user",
            details={"reason": "privileged_role_not_allowed", "role": role},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{role} accounts must be created by an administrator.",
        )
    if role.lower() != "candidate":
        audit.log_event(
            db,
            actor=payload.email,
            action="register_failure",
            target_type="user",
            details={"reason": "invalid_role", "role": role},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Public registration only allows role 'Candidate'.",
        )
    payload.job_title = "Candidate"

    # Duplicate-email check
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        audit.log_event(
            db,
            actor=payload.email,
            action="register_failure",
            target_type="user",
            details={"reason": "duplicate_email"},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    now_utc = datetime.now(timezone.utc)
    db_user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        company_name=payload.company_name,
        job_title=payload.job_title,
        phone_number=payload.phone_number,
        last_login_at=now_utc,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    audit.log_event(
        db,
        actor=db_user,
        action="register_success",
        target_type="user",
        target_id=db_user.user_id,
        details={"email": db_user.email, "role": db_user.job_title},
    )

    token = create_access_token({"sub": db_user.email})
    return Token(access_token=token, user=UserResponse.from_orm_model(db_user))


def _authenticate_and_finalize_login(user: User, payload: UserLogin, db: Session) -> Token:
    if user.job_title not in SUPPORTED_ROLES:
        audit.log_event(
            db,
            actor=user.email,
            action="login_failure",
            target_type="user",
            target_id=user.user_id,
            details={"reason": "role_retired"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The HR Manager role has been retired and is no longer supported. Please contact your administrator.",
        )
    if not user.is_active:
        audit.log_event(
            db,
            actor=user.email,
            action="login_failure",
            target_type="user",
            target_id=user.user_id,
            details={"reason": "account_disabled"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is disabled. Contact your administrator.",
        )
    if payload.role and payload.role.strip().lower() != (user.job_title or "").strip().lower():
        audit.log_event(
            db,
            actor=user.email,
            action="login_failure",
            target_type="user",
            target_id=user.user_id,
            details={"reason": "role_mismatch", "attempted_role": payload.role, "user_role": user.job_title},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This account is not registered as a {payload.role}. Select the correct role to sign in.",
        )
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    audit.log_event(
        db,
        actor=user,
        action="login_success",
        target_type="user",
        target_id=user.user_id,
        details={"email": user.email, "role": user.job_title},
    )
    token = create_access_token({"sub": user.email})
    return Token(access_token=token, user=UserResponse.from_orm_model(user))


@app.post("/api/auth/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    ident = payload.email.strip()
    ident_lower = ident.lower()

    # 1. Primary lookup by exact email match
    exact_user = db.query(User).filter(func.lower(User.email) == ident_lower).first()
    if exact_user and verify_password(payload.password, exact_user.password_hash):
        return _authenticate_and_finalize_login(exact_user, payload, db)

    # 2. Secondary lookup by account username / full_name or email prefix
    candidates_matching = (
        db.query(User)
        .filter(
            or_(
                func.lower(User.email) == ident_lower,
                func.lower(User.full_name) == ident_lower,
                func.lower(User.email).like(f"{ident_lower}@%"),
            )
        )
        .all()
    )
    for u in candidates_matching:
        if verify_password(payload.password, u.password_hash):
            return _authenticate_and_finalize_login(u, payload, db)

    audit.log_event(
        db,
        actor=ident,
        action="login_failure",
        target_type="user",
        details={"reason": "invalid_credentials"},
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.from_orm_model(current_user)


@app.get("/api/auth/profile", response_model=UserResponse)
def get_profile(
    current_user: User = Depends(require_roles("Recruiter", "Admin")),
):
    return UserResponse.from_orm_model(current_user)


@app.put("/api/auth/profile", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(require_roles("Recruiter", "Admin")),
    db: Session = Depends(get_db),
):
    changed = {}
    data = payload.model_dump(exclude_unset=True)

    if "full_name" in data and data["full_name"] != current_user.full_name:
        changed["full_name"] = {"from": current_user.full_name, "to": data["full_name"]}
        current_user.full_name = data["full_name"]

    if "company_name" in data and data["company_name"] != current_user.company_name:
        changed["company_name"] = {"from": current_user.company_name, "to": data["company_name"]}
        current_user.company_name = data["company_name"]

    if "phone_number" in data and data["phone_number"] != current_user.phone_number:
        changed["phone_number"] = {"from": current_user.phone_number, "to": data["phone_number"]}
        current_user.phone_number = data["phone_number"]

    if changed:
        db.commit()
        db.refresh(current_user)
        audit.log_event(
            db,
            actor=current_user,
            action="update_profile",
            target_type="user",
            target_id=current_user.user_id,
            details={"changed": changed},
        )

    return UserResponse.from_orm_model(current_user)


@app.post("/api/auth/change-password")
def change_password(
    payload: PasswordChange,
    current_user: User = Depends(require_roles("Recruiter", "Admin")),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        audit.log_event(
            db,
            actor=current_user,
            action="change_password_failure",
            target_type="user",
            target_id=current_user.user_id,
            details={"reason": "invalid_current_password"},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    db.refresh(current_user)

    audit.log_event(
        db,
        actor=current_user,
        action="change_password",
        target_type="user",
        target_id=current_user.user_id,
        details={"email": current_user.email},
    )

    return {"message": "Password changed successfully."}


# ---------------------------------------------------------------------------
# Admin routes (Phase 2)
# ---------------------------------------------------------------------------
from admin_routes import router as admin_router
app.include_router(admin_router)


@app.get("/api/settings")
def get_public_settings(db: Session = Depends(get_db)):
    """Return public platform configuration and feature flags."""
    return {k: settings_store.get_setting(db, k) for k in settings_store.DEFAULT_SETTINGS}


# ---------------------------------------------------------------------------
# Candidate endpoints  (all protected — require valid JWT)
# ---------------------------------------------------------------------------

@app.post("/api/candidates/upload", response_model=CandidateResponse)
async def upload_candidate(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    safe_filename = os.path.basename(file.filename or "resume.pdf")
    ext = os.path.splitext(safe_filename)[1].lower()
    if ext not in [".pdf", ".docx", ".txt"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload a .pdf, .docx, or .txt resume.",
        )

    os.makedirs("uploads", exist_ok=True)
    file_path = os.path.join("uploads", safe_filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    try:
        raw_text = file_loader.extract_text(file_path)
        parsed_data = parser.extract_candidate_info(raw_text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")

    db_candidate = None
    email_val = parsed_data.get("email")
    if email_val:
        db_candidate = db.query(Candidate).filter(
            Candidate.email == email_val,
            Candidate.deleted_at.is_(None),
        ).first()
    if not db_candidate:
        db_candidate = db.query(Candidate).filter(
            Candidate.resume_path == safe_filename,
            Candidate.deleted_at.is_(None),
        ).first()

    if db_candidate:
        db_candidate.name = parsed_data.get("name") or db_candidate.name
        db_candidate.email = email_val or db_candidate.email
        db_candidate.phone = parsed_data.get("phone") or db_candidate.phone
        db_candidate.education = json.dumps(parsed_data.get("education", []))
        db_candidate.skills = json.dumps(parsed_data.get("skills", []))
        db_candidate.experience = json.dumps(parsed_data.get("experience", []))
        db_candidate.certifications = json.dumps(parsed_data.get("certifications", []))
        db_candidate.projects = json.dumps(parsed_data.get("projects", []))
        db_candidate.resume_path = safe_filename
    else:
        db_candidate = Candidate(
            name=parsed_data.get("name"),
            email=email_val,
            phone=parsed_data.get("phone"),
            education=json.dumps(parsed_data.get("education", [])),
            skills=json.dumps(parsed_data.get("skills", [])),
            experience=json.dumps(parsed_data.get("experience", [])),
            certifications=json.dumps(parsed_data.get("certifications", [])),
            projects=json.dumps(parsed_data.get("projects", [])),
            resume_path=safe_filename,
        )
        db.add(db_candidate)

    db.commit()
    db.refresh(db_candidate)

    existing_app = db.query(Application).filter(Application.candidate_id == db_candidate.candidate_id).first()
    if not existing_app:
        db_candidate.stage = "new"
        new_app = Application(
            candidate_id=db_candidate.candidate_id,
            recruiter_id=_user.user_id,
            stage="new",
            stage_history=json.dumps([{
                "from_stage": None,
                "to_stage": "new",
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "updated_by": _user.email,
                "notes": "Added via resume upload"
            }]),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(new_app)
        db.commit()

    return CandidateResponse.from_orm_model(db_candidate)


@app.get("/api/candidates", response_model=CandidateListResponse)
def get_candidates(
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(100, ge=1, le=50000),
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    query = db.query(Candidate).filter(Candidate.deleted_at.is_(None))
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Candidate.name.ilike(pattern),
                Candidate.email.ilike(pattern),
                Candidate.skills.ilike(pattern),
            )
        )
    total = query.count()
    candidates = query.offset(skip).limit(limit).all()
    return CandidateListResponse(
        total=total,
        candidates=[CandidateResponse.from_orm_model(c) for c in candidates],
    )


def _candidate_to_dict(c: Candidate) -> dict:
    """Helper to convert a Candidate ORM object into a clean dictionary with parsed JSON fields."""
    def _parse_json(field_str):
        if not field_str:
            return []
        try:
            val = json.loads(field_str)
            return val if isinstance(val, list) else []
        except Exception:
            return []

    return {
        "candidate_id": c.candidate_id,
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "skills": _parse_json(c.skills),
        "education": _parse_json(c.education),
        "experience": _parse_json(c.experience),
        "certifications": _parse_json(c.certifications),
        "projects": _parse_json(c.projects),
        "resume_path": c.resume_path,
        "stage": (c.stage or "new").lower(),
    }


def _load_candidates_as_dicts(db: Session) -> List[dict]:
    """Helper to load all Candidate rows into deserialized dictionaries."""
    candidates = db.query(Candidate).filter(Candidate.deleted_at.is_(None)).all()
    return [_candidate_to_dict(c) for c in candidates]


def _job_to_dict(job: Job) -> dict:
    """Helper to convert a Job ORM object into a dictionary with parsed skill lists."""
    def _parse_list(text):
        if not text:
            return []
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    return {
        "job_id": job.job_id,
        "title": job.title,
        "description": job.description,
        "department": job.department,
        "location": job.location,
        "employment_type": job.employment_type,
        "required_skills": _parse_list(job.required_skills),
        "nice_to_have_skills": _parse_list(job.nice_to_have_skills),
        "min_experience_years": job.min_experience_years,
        "seniority": job.seniority,
    }


def _pipeline_match_score(cand_row: Any, job_row: Any) -> Optional[float]:
    """Compute candidate-job match score for pipeline cards and details."""
    if not cand_row or not job_row:
        return None
    try:
        cand_dict = _candidate_to_dict(cand_row) if not isinstance(cand_row, dict) else cand_row
        job_dict = _job_to_dict(job_row) if not isinstance(job_row, dict) else job_row
        score_data = matching_engine.score_candidate(
            candidate_skills=cand_dict.get("skills", []),
            candidate_experience=cand_dict.get("experience", []),
            job=job_dict,
        )
        score_val = score_data.get("final_score")
        if score_val is None:
            score_val = score_data.get("overall_score")
        if score_val is not None:
            return round(float(score_val), 1)
        return None
    except Exception as e:
        logger.warning(
            "Failed computing pipeline match score for candidate %s, job %s: %s",
            getattr(cand_row, "candidate_id", None),
            getattr(job_row, "job_id", None),
            e,
        )
        return None


@app.get("/api/candidates/hiring-scores", response_model=List[HiringScoreBreakdown])
def get_candidates_hiring_scores(
    job_id: Optional[int] = None,
    skip: int = 0,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    """
    Compute and return job-independent Hiring Scores for all candidates, sorted descending.
    When optional ?job_id= is supplied, computes blended_score and sorts by blended_score descending.
    """
    job_dict = None
    if job_id is not None:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job_dict = _job_to_dict(job)

    candidates = _load_candidates_as_dicts(db)
    results: List[HiringScoreBreakdown] = []

    for c in candidates:
        hs_breakdown = hiring_score.calculate_hiring_score(c)
        blended = None

        if job_dict is not None:
            match_res = matching_engine.score_candidate(
                candidate_skills=c.get("skills", []),
                candidate_experience=c.get("experience", []),
                job=job_dict,
            )
            blended = hiring_score.blend_with_job_match(
                hiring_score=hs_breakdown["hiring_score"],
                job_match_final_score=match_res["final_score"],
            )

        results.append(HiringScoreBreakdown(
            candidate_id=c.get("candidate_id"),
            candidate_name=c.get("name"),
            email=c.get("email"),
            source_file=c.get("resume_path"),
            blended_score=blended,
            **hs_breakdown,
        ))

    if job_id is not None:
        results.sort(key=lambda x: (x.blended_score if x.blended_score is not None else -1.0), reverse=True)
    else:
        results.sort(key=lambda x: x.hiring_score, reverse=True)

    if limit is not None and limit > 0:
        return results[skip : skip + limit]
    return results[skip:]


@app.get("/api/candidates/{candidate_id}/hiring-score", response_model=HiringScoreBreakdown)
def get_candidate_hiring_score(
    candidate_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    """
    Compute and return the detailed job-independent Hiring Score breakdown for a single candidate.
    """
    candidate = db.query(Candidate).filter(
        Candidate.candidate_id == candidate_id,
        Candidate.deleted_at.is_(None),
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    cand_dict = _candidate_to_dict(candidate)
    hs_breakdown = hiring_score.calculate_hiring_score(cand_dict)

    return HiringScoreBreakdown(
        candidate_id=candidate.candidate_id,
        candidate_name=candidate.name,
        email=candidate.email,
        source_file=candidate.resume_path,
        **hs_breakdown,
    )


@app.get("/api/candidates/{candidate_id}", response_model=CandidateResponse)
def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    candidate = db.query(Candidate).filter(
        Candidate.candidate_id == candidate_id,
        Candidate.deleted_at.is_(None),
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return CandidateResponse.from_orm_model(candidate)


@app.delete("/api/candidates/{candidate_id}")
def delete_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    candidate = db.query(Candidate).filter(
        Candidate.candidate_id == candidate_id,
        Candidate.deleted_at.is_(None),
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.deleted_at = datetime.now(timezone.utc)
    db.query(Application).filter(Application.candidate_id == candidate_id).delete()
    db.query(InterviewSession).filter(InterviewSession.candidate_id == candidate_id).delete()
    db.query(ResumeAnalysis).filter(ResumeAnalysis.candidate_id == candidate_id).delete()
    db.query(PracticeAnswer).filter(PracticeAnswer.candidate_id == candidate_id).delete()
    audit.log_event(
        db,
        actor=_user,
        action="delete_candidate",
        target_type="candidate",
        target_id=candidate_id,
        details={"name": candidate.name, "email": candidate.email},
    )
    db.commit()
    return {"message": "Candidate deleted successfully"}


@app.delete("/api/candidates")
def delete_all_candidates(
    _user: User = Depends(require_recruiter),
):
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Bulk deletion of candidates is disabled. Use the admin purge API or delete individually.",
    )


# ---------------------------------------------------------------------------
# Recruitment Pipeline Endpoints
# ---------------------------------------------------------------------------

def _get_candidate_initials(name: Optional[str]) -> str:
    if not name or not name.strip():
        return "CN"
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    elif len(parts) == 1 and len(parts[0]) > 0:
        return parts[0][:2].upper()
    return "CN"


@app.get("/api/pipeline", response_model=PipelineBoardResponse)
def get_recruitment_pipeline(
    job_id: Optional[int] = None,
    search: Optional[str] = None,
    stage: Optional[str] = None,
    skill: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    """
    Returns the six-stage recruitment pipeline board with candidate cards.
    Stage counts reflect persistent database totals.
    Accessible exclusively to Recruiters.
    """
    # Base query for all applications
    apps_query = db.query(Application, Candidate, Job).join(
        Candidate, Application.candidate_id == Candidate.candidate_id
    ).outerjoin(
        Job, Application.job_id == Job.job_id
    ).filter(
        Candidate.deleted_at.is_(None)
    )

    all_apps = apps_query.all()

    # Pre-compute total stage counts across the whole database
    counts = {s: 0 for s in VALID_PIPELINE_STAGES}
    for app_row, cand_row, _ in all_apps:
        stg = (app_row.stage or "new").lower()
        if stg in counts:
            counts[stg] += 1
        else:
            counts["new"] += 1
    counts["total"] = len(all_apps)

    filtered_stages = {s: [] for s in VALID_PIPELINE_STAGES}
    filtered_counts = {s: 0 for s in VALID_PIPELINE_STAGES}

    search_norm = search.strip().lower() if search and search.strip() else None
    stage_filter = stage.strip().lower() if stage and stage.strip() else None
    skill_filter = skill.strip().lower() if skill and skill.strip() else None

    for app_row, cand_row, job_row in all_apps:
        # Check Job filter
        if job_id is not None and app_row.job_id != job_id:
            continue

        # Check Stage filter
        app_stage = (app_row.stage or "new").lower()
        if app_stage not in VALID_PIPELINE_STAGES:
            app_stage = "new"
        if stage_filter and app_stage != stage_filter:
            continue

        # Parse skills
        cand_skills = []
        if cand_row.skills:
            try:
                raw_sk = json.loads(cand_row.skills)
                cand_skills = raw_sk if isinstance(raw_sk, list) else []
            except Exception:
                cand_skills = []

        # Check Skill filter
        if skill_filter:
            if not any(skill_filter in s.lower() for s in cand_skills):
                continue

        # Check Search filter (name, email, skills)
        if search_norm:
            cand_name = (cand_row.name or "").lower()
            cand_email = (cand_row.email or "").lower()
            skills_text = " ".join([s.lower() for s in cand_skills])
            if (search_norm not in cand_name and
                search_norm not in cand_email and
                search_norm not in skills_text):
                continue

        # Parse history
        history = []
        if app_row.stage_history:
            try:
                hist_raw = json.loads(app_row.stage_history)
                history = hist_raw if isinstance(hist_raw, list) else []
            except Exception:
                history = []

        # Calculate match score via shared helper
        match_score = _pipeline_match_score(cand_row, job_row)

        card = ApplicationCardResponse(
            application_id=app_row.application_id,
            candidate_id=cand_row.candidate_id,
            candidate_name=cand_row.name or "Unnamed Candidate",
            candidate_email=cand_row.email,
            candidate_phone=cand_row.phone,
            candidate_initials=_get_candidate_initials(cand_row.name),
            job_id=job_row.job_id if job_row else None,
            job_title=job_row.title if job_row else "General Applicant",
            skills=cand_skills,
            stage=app_stage,
            match_score=match_score,
            notes=app_row.notes,
            resume_path=cand_row.resume_path,
            stage_history=history,
            created_at=app_row.created_at.strftime("%Y-%m-%d %H:%M") if app_row.created_at else "",
            updated_at=app_row.updated_at.strftime("%Y-%m-%d %H:%M") if app_row.updated_at else "",
        )

        filtered_stages[app_stage].append(card)
        filtered_counts[app_stage] += 1

    filtered_counts["total"] = sum(filtered_counts[s] for s in VALID_PIPELINE_STAGES)

    return PipelineBoardResponse(
        stages=filtered_stages,
        counts=counts,
        filtered_counts=filtered_counts,
        total_applications=counts["total"]
    )


@app.patch("/api/pipeline/applications/{application_id}/stage", response_model=ApplicationCardResponse)
def update_application_stage(
    application_id: int,
    payload: ApplicationStageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    """
    Moves an application card between hiring stages.
    Persists stage update and records audit log in stage_history.
    """
    new_stage = payload.stage.strip().lower()
    if new_stage not in VALID_PIPELINE_STAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage '{payload.stage}'. Must be one of: {', '.join(VALID_PIPELINE_STAGES)}"
        )

    app_row = db.query(Application).filter(Application.application_id == application_id).first()
    if not app_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    cand_row = db.query(Candidate).filter(Candidate.candidate_id == app_row.candidate_id).first()
    if not cand_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated candidate not found.")

    job_row = db.query(Job).filter(Job.job_id == app_row.job_id).first() if app_row.job_id else None

    old_stage = app_row.stage
    now_utc = datetime.now(timezone.utc)

    history = []
    if app_row.stage_history:
        try:
            h_raw = json.loads(app_row.stage_history)
            history = h_raw if isinstance(h_raw, list) else []
        except Exception:
            history = []

    history.append({
        "from_stage": old_stage,
        "to_stage": new_stage,
        "timestamp": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "updated_by": current_user.email,
        "notes": payload.notes or ""
    })

    app_row.stage = new_stage
    if payload.notes is not None:
        app_row.notes = payload.notes
    app_row.stage_history = json.dumps(history)
    app_row.updated_at = now_utc

    cand_row.stage = new_stage

    db.commit()
    db.refresh(app_row)

    cand_skills = []
    if cand_row.skills:
        try:
            raw_sk = json.loads(cand_row.skills)
            cand_skills = raw_sk if isinstance(raw_sk, list) else []
        except Exception:
            cand_skills = []

    match_score = _pipeline_match_score(cand_row, job_row)

    return ApplicationCardResponse(
        application_id=app_row.application_id,
        candidate_id=cand_row.candidate_id,
        candidate_name=cand_row.name or "Unnamed Candidate",
        candidate_email=cand_row.email,
        candidate_phone=cand_row.phone,
        candidate_initials=_get_candidate_initials(cand_row.name),
        job_id=job_row.job_id if job_row else None,
        job_title=job_row.title if job_row else "General Applicant",
        skills=cand_skills,
        stage=app_row.stage,
        match_score=match_score,
        notes=app_row.notes,
        resume_path=cand_row.resume_path,
        stage_history=history,
        created_at=app_row.created_at.strftime("%Y-%m-%d %H:%M") if app_row.created_at else "",
        updated_at=app_row.updated_at.strftime("%Y-%m-%d %H:%M") if app_row.updated_at else "",
    )


@app.patch("/api/candidates/{candidate_id}/stage")
def update_candidate_stage_direct(
    candidate_id: int,
    payload: ApplicationStageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    """Convenience endpoint to update stage by candidate ID."""
    new_stage = payload.stage.strip().lower()
    if new_stage not in VALID_PIPELINE_STAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage '{payload.stage}'."
        )

    cand = db.query(Candidate).filter(
        Candidate.candidate_id == candidate_id,
        Candidate.deleted_at.is_(None),
    ).first()
    if not cand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")

    cand.stage = new_stage
    app_row = db.query(Application).filter(Application.candidate_id == candidate_id).order_by(Application.application_id.desc()).first()
    if app_row:
        app_row.stage = new_stage
        app_row.updated_at = datetime.now(timezone.utc)

    db.commit()
    return {"candidate_id": candidate_id, "stage": new_stage}


@app.patch("/api/pipeline/applications/{application_id}/notes")
def update_application_notes(
    application_id: int,
    payload: ApplicationNotesUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    app_row = db.query(Application).filter(Application.application_id == application_id).first()
    if not app_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
    app_row.notes = payload.notes
    app_row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"application_id": application_id, "notes": app_row.notes}


@app.post("/api/pipeline/applications", response_model=ApplicationCardResponse, status_code=status.HTTP_201_CREATED)
def add_application_to_pipeline(
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    """
    Associates an existing candidate with a job position in the pipeline.
    Prevents duplicate entries for the same candidate and job.
    """
    cand = db.query(Candidate).filter(
        Candidate.candidate_id == payload.candidate_id,
        Candidate.deleted_at.is_(None),
    ).first()
    if not cand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")

    job = db.query(Job).filter(Job.job_id == payload.job_id).first() if payload.job_id else None

    # Check for duplicate
    dup_filter = (Application.candidate_id == payload.candidate_id)
    if payload.job_id:
        dup_filter = dup_filter & (Application.job_id == payload.job_id)
    else:
        dup_filter = dup_filter & (Application.job_id.is_(None))

    existing = db.query(Application).filter(dup_filter).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidate is already in the pipeline for this position."
        )

    initial_stage = (payload.stage or "new").strip().lower()
    now_utc = datetime.now(timezone.utc)
    history = [{
        "from_stage": None,
        "to_stage": initial_stage,
        "timestamp": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "updated_by": current_user.email,
        "notes": payload.notes or "Added to pipeline"
    }]

    new_app = Application(
        candidate_id=cand.candidate_id,
        job_id=job.job_id if job else None,
        recruiter_id=current_user.user_id,
        stage=initial_stage,
        notes=payload.notes,
        stage_history=json.dumps(history),
        created_at=now_utc,
        updated_at=now_utc,
    )
    cand.stage = initial_stage
    db.add(new_app)
    db.commit()
    db.refresh(new_app)

    cand_skills = []
    if cand.skills:
        try:
            raw_sk = json.loads(cand.skills)
            cand_skills = raw_sk if isinstance(raw_sk, list) else []
        except Exception:
            cand_skills = []

    match_score = _pipeline_match_score(cand, job)

    return ApplicationCardResponse(
        application_id=new_app.application_id,
        candidate_id=cand.candidate_id,
        candidate_name=cand.name or "Unnamed Candidate",
        candidate_email=cand.email,
        candidate_phone=cand.phone,
        candidate_initials=_get_candidate_initials(cand.name),
        job_id=job.job_id if job else None,
        job_title=job.title if job else "General Applicant",
        skills=cand_skills,
        stage=new_app.stage,
        match_score=match_score,
        notes=new_app.notes,
        resume_path=cand.resume_path,
        stage_history=history,
        created_at=new_app.created_at.strftime("%Y-%m-%d %H:%M") if new_app.created_at else "",
        updated_at=new_app.updated_at.strftime("%Y-%m-%d %H:%M") if new_app.updated_at else "",
    )


@app.post("/api/pipeline/candidates", response_model=ApplicationCardResponse, status_code=status.HTTP_201_CREATED)
def create_candidate_and_pipeline(
    payload: CandidateAddPipeline,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    """
    Registers a new candidate record and creates an initial pipeline entry.
    """
    email_clean = payload.email.strip().lower()
    existing_cand = db.query(Candidate).filter(
        func.lower(Candidate.email) == email_clean,
        Candidate.deleted_at.is_(None),
    ).first()
    if existing_cand:
        cand = existing_cand
    else:
        cand_skills = payload.skills
        if isinstance(cand_skills, str):
            cand_skills = [s.strip() for s in cand_skills.split(",") if s.strip()]
        elif not cand_skills:
            cand_skills = []

        cand_edu = payload.education
        if isinstance(cand_edu, str):
            cand_edu = [{"degree": cand_edu.strip()}] if cand_edu.strip() else []
        elif not cand_edu:
            cand_edu = []

        cand_exp = payload.experience
        if isinstance(cand_exp, str):
            cand_exp = [{"title": cand_exp.strip()}] if cand_exp.strip() else []
        elif not cand_exp:
            cand_exp = []

        cand = Candidate(
            name=payload.name.strip(),
            email=email_clean,
            phone=payload.phone.strip() if payload.phone else None,
            skills=json.dumps(cand_skills),
            education=json.dumps(cand_edu),
            experience=json.dumps(cand_exp),
            stage=payload.stage or "new",
            created_at=datetime.now(timezone.utc)
        )
        db.add(cand)
        db.commit()
        db.refresh(cand)

    job = db.query(Job).filter(Job.job_id == payload.job_id).first() if payload.job_id else None
    dup_q = db.query(Application).filter(Application.candidate_id == cand.candidate_id)
    if payload.job_id:
        dup_q = dup_q.filter(Application.job_id == payload.job_id)
    else:
        dup_q = dup_q.filter(Application.job_id.is_(None))

    existing_app = dup_q.first()
    if existing_app:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidate already has an application entry for this position."
        )

    initial_stage = (payload.stage or "new").strip().lower()
    now_utc = datetime.now(timezone.utc)
    history = [{
        "from_stage": None,
        "to_stage": initial_stage,
        "timestamp": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "updated_by": current_user.email,
        "notes": payload.notes or "Created and added to pipeline"
    }]

    new_app = Application(
        candidate_id=cand.candidate_id,
        job_id=job.job_id if job else None,
        recruiter_id=current_user.user_id,
        stage=initial_stage,
        notes=payload.notes,
        stage_history=json.dumps(history),
        created_at=now_utc,
        updated_at=now_utc,
    )
    cand.stage = initial_stage
    db.add(new_app)
    db.commit()
    db.refresh(new_app)
    cand_skills = []
    if cand.skills:
        try:
            raw_sk = json.loads(cand.skills)
            cand_skills = raw_sk if isinstance(raw_sk, list) else []
        except Exception:
            cand_skills = []
    match_score = _pipeline_match_score(cand, job)

    return ApplicationCardResponse(
        application_id=new_app.application_id,
        candidate_id=cand.candidate_id,
        candidate_name=cand.name or "Unnamed Candidate",
        candidate_email=cand.email,
        candidate_phone=cand.phone,
        candidate_initials=_get_candidate_initials(cand.name),
        job_id=job.job_id if job else None,
        job_title=job.title if job else "General Applicant",
        skills=cand_skills,
        stage=new_app.stage,
        match_score=match_score,
        notes=new_app.notes,
        resume_path=cand.resume_path,
        stage_history=history,
        created_at=new_app.created_at.strftime("%Y-%m-%d %H:%M") if new_app.created_at else "",
        updated_at=new_app.updated_at.strftime("%Y-%m-%d %H:%M") if new_app.updated_at else "",
    )


@app.get("/api/pipeline/applications/{application_id}", response_model=CandidatePipelineDetailResponse)
def get_pipeline_application_detail(
    application_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    """
    Returns full profile, match evaluation, recruiter notes, interview history, and stage audit log.
    """
    app_row = db.query(Application).filter(Application.application_id == application_id).first()
    if not app_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    cand = db.query(Candidate).filter(Candidate.candidate_id == app_row.candidate_id).first()
    if not cand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated candidate not found.")

    job = db.query(Job).filter(Job.job_id == app_row.job_id).first() if app_row.job_id else None

    def _parse_list(field):
        if not field:
            return []
        try:
            val = json.loads(field)
            return val if isinstance(val, list) else []
        except Exception:
            return []

    skills = _parse_list(cand.skills)
    education = _parse_list(cand.education)
    experience = _parse_list(cand.experience)
    certifications = _parse_list(cand.certifications)
    projects = _parse_list(cand.projects)
    stage_history = _parse_list(app_row.stage_history)

    match_score = None
    match_breakdown = None
    if job:
        try:
            cand_dict = _candidate_to_dict(cand)
            job_dict = _job_to_dict(job)
            match_breakdown = matching_engine.score_candidate(
                candidate_skills=cand_dict.get("skills", []),
                candidate_experience=cand_dict.get("experience", []),
                job=job_dict,
            )
            score_val = match_breakdown.get("final_score")
            if score_val is None:
                score_val = match_breakdown.get("overall_score")
            if score_val is not None:
                match_score = round(float(score_val), 1)
        except Exception as e:
            logger.warning("Error computing match breakdown for candidate %s, job %s: %s", getattr(cand, "candidate_id", None), getattr(job, "job_id", None), e)

    interviews = []
    sess_query = db.query(InterviewSession).filter(InterviewSession.candidate_id == cand.candidate_id).all()
    for s in sess_query:
        fb_dict = None
        if s.feedback:
            try:
                fb_dict = json.loads(s.feedback)
            except Exception:
                pass
        interviews.append({
            "session_id": s.session_id,
            "job_id": s.job_id,
            "status": s.status,
            "difficulty": s.difficulty,
            "interview_type": s.interview_type,
            "created_at": s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else "",
            "feedback": fb_dict
        })

    job_req_skills = []
    if job and job.required_skills:
        try:
            raw_req = json.loads(job.required_skills)
            job_req_skills = raw_req if isinstance(raw_req, list) else []
        except Exception:
            pass

    return CandidatePipelineDetailResponse(
        application_id=app_row.application_id,
        candidate_id=cand.candidate_id,
        name=cand.name or "Unnamed Candidate",
        email=cand.email,
        phone=cand.phone,
        skills=skills,
        education=education,
        experience=experience,
        certifications=certifications,
        projects=projects,
        resume_path=cand.resume_path,
        job_id=job.job_id if job else None,
        job_title=job.title if job else "General Applicant",
        job_department=job.department if job else None,
        job_required_skills=job_req_skills,
        stage=app_row.stage,
        match_score=match_score,
        match_breakdown=match_breakdown,
        notes=app_row.notes,
        stage_history=stage_history,
        interviews=interviews,
        created_at=app_row.created_at.strftime("%Y-%m-%d %H:%M") if app_row.created_at else "",
        updated_at=app_row.updated_at.strftime("%Y-%m-%d %H:%M") if app_row.updated_at else "",
    )


def _compute_skill_stats(db: Session):
    """Shared helper: scan every Candidate and return aggregate skill data.

    Returns:
        (candidates_total, resumes_parsed, all_skills, counts)
        - candidates_total: number of Candidate rows
        - resumes_parsed: candidates that have at least one parseable skill
        - all_skills: flat list of every normalised skill token (with repeats)
        - counts: Counter mapping each unique skill -> occurrence count
    """
    candidates = db.query(Candidate).filter(Candidate.deleted_at.is_(None)).all()
    candidates_total = len(candidates)
    resumes_parsed = 0
    all_skills: list[str] = []
    for candidate in candidates:
        if candidate.skills:
            try:
                skills = json.loads(candidate.skills)
                normalised = [s.strip().lower() for s in skills if isinstance(s, str)]
                if normalised:
                    resumes_parsed += 1
                    all_skills.extend(normalised)
            except Exception:
                pass
    counts = Counter(all_skills)
    return candidates_total, resumes_parsed, all_skills, counts


@app.get("/api/analytics/summary", response_model=AnalyticsSummary)
def get_analytics_summary(
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    """Top-level dashboard stats (independent of list pagination)."""
    candidates_total, resumes_parsed, all_skills, counts = _compute_skill_stats(db)
    unique_skills = len(counts)
    total_occurrences = len(all_skills)
    avg_per_candidate = (
        round(total_occurrences / candidates_total, 2) if candidates_total else 0.0
    )
    return AnalyticsSummary(
        total_candidates=candidates_total,
        unique_skills=unique_skills,
        total_skill_occurrences=total_occurrences,
        avg_skills_per_candidate=avg_per_candidate,
        resumes_parsed=resumes_parsed,
    )


@app.get("/api/analytics/skills", response_model=List[SkillFrequency])
def get_skills_analytics(
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    _total, _parsed, _all, counts = _compute_skill_stats(db)
    return [SkillFrequency(skill=format_skill_display(skill), count=count) for skill, count in counts.most_common()]



# ---------------------------------------------------------------------------
# Job Management Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/jobs", response_model=JobResponse, status_code=201)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    db_job = Job(
        title=payload.title,
        description=payload.description,
        department=payload.department,
        location=payload.location,
        employment_type=payload.employment_type,
        seniority=payload.seniority,
        min_experience_years=payload.min_experience_years,
        required_skills=json.dumps(payload.required_skills or []),
        nice_to_have_skills=json.dumps(payload.nice_to_have_skills or []),
        status=(payload.status or "open").strip().lower(),
        created_by=current_user.user_id,
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return JobResponse.from_orm_model(db_job)


@app.get("/api/jobs", response_model=List[JobResponse])
def get_jobs(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    query = db.query(Job)
    if status:
        query = query.filter(func.lower(Job.status) == status.strip().lower())
    jobs = query.order_by(Job.created_at.desc()).all()
    return [JobResponse.from_orm_model(j) for j in jobs]


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.from_orm_model(job)


@app.put("/api/jobs/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if payload.title is not None:
        job.title = payload.title
    if payload.description is not None:
        job.description = payload.description
    if payload.department is not None:
        job.department = payload.department
    if payload.location is not None:
        job.location = payload.location
    if payload.employment_type is not None:
        job.employment_type = payload.employment_type
    if payload.seniority is not None:
        job.seniority = payload.seniority
    if payload.min_experience_years is not None:
        job.min_experience_years = payload.min_experience_years
    if payload.required_skills is not None:
        job.required_skills = json.dumps(payload.required_skills)
    if payload.nice_to_have_skills is not None:
        job.nice_to_have_skills = json.dumps(payload.nice_to_have_skills)
    if payload.status is not None:
        job.status = payload.status.strip().lower()

    db.commit()
    db.refresh(job)
    return JobResponse.from_orm_model(job)


@app.delete("/api/jobs/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.query(Application).filter(Application.job_id == job_id).update({Application.job_id: None})
    db.query(InterviewSession).filter(InterviewSession.job_id == job_id).delete()
    db.query(ResumeAnalysis).filter(ResumeAnalysis.target_job_id == job_id).update({ResumeAnalysis.target_job_id: None})
    db.query(PracticeAnswer).filter(PracticeAnswer.job_id == job_id).update({PracticeAnswer.job_id: None})
    db.delete(job)
    db.commit()
    return {"message": "Job deleted successfully"}


# ---------------------------------------------------------------------------
# Matching Helpers & Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/jobs/{job_id}/match", response_model=List[MatchBreakdown])
def match_candidates_for_job(
    job_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    """
    Match and rank candidates against a persisted Job record.
    Returns detailed multi-factor breakdown.
    """
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job_dict = _job_to_dict(job)
    candidates = _load_candidates_as_dicts(db)
    if not candidates:
        return []

    ranked = matching_engine.rank_candidates(job_dict, candidates)
    return [MatchBreakdown(**item) for item in ranked]


class MatchRequest(BaseModel):
    required_skills: str


@app.post("/api/match", response_model=List[MatchResult])
def match_candidates(
    req: MatchRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    """
    Backward-compatible quick match endpoint accepting free-text required skills.
    Delegates to the matching engine under the hood and returns legacy MatchResult shape.
    """
    required_skills_list = [s.strip() for s in req.required_skills.split(",") if s.strip()]
    if not required_skills_list:
        return []

    candidates = _load_candidates_as_dicts(db)
    if not candidates:
        return []

    # Build ephemeral job specification
    job_dict = {
        "title": "Quick Match",
        "required_skills": required_skills_list,
        "nice_to_have_skills": [],
        "min_experience_years": None,
        "seniority": None,
    }

    ranked = matching_engine.rank_candidates(job_dict, candidates)

    # Map engine breakdown back to MatchResult for backward compatibility
    results = []
    for item in ranked:
        results.append(MatchResult(
            candidate_name=item.get("candidate_name"),
            email=item.get("email"),
            match_score=round(item.get("final_score", 0.0), 2),
            matched_skills=item.get("matched_required", []),
            missing_skills=item.get("missing_required", []),
            source_file=item.get("source_file"),
        ))

    return results


# ---------------------------------------------------------------------------
# Skill Gap Analysis Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/jobs/{job_id}/skill-gap-report/export")
def export_skill_gap_report(
    job_id: int,
    format: Literal["csv", "docx"] = "csv",
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    """
    Export skill gap report as downloadable CSV or DOCX document.
    """
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job_dict = _job_to_dict(job)
    candidates = _load_candidates_as_dicts(db)
    report = skill_gap_analysis.analyze_job_skill_gaps(job_dict, candidates)

    if format == "csv":
        all_gaps = report["critical_gaps"] + report["moderate_gaps"] + report["minor_gaps"]
        if all_gaps:
            df = pd.DataFrame(all_gaps)[["skill", "category", "severity", "missing_count", "missing_percentage"]]
        else:
            df = pd.DataFrame(columns=["skill", "category", "severity", "missing_count", "missing_percentage"])

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="skill_gap_report_job_{job_id}.csv"'},
        )
    elif format == "docx":
        doc = Document()
        doc.add_heading("SmartHire AI — Skill Gap Analysis Report", level=0)
        doc.add_paragraph(f"Job Position: {report['job_title']} (Job ID: {report['job_id']})")
        doc.add_paragraph(f"Generated At: {report['generated_at']}")
        doc.add_paragraph(f"Total Candidates Analyzed: {report['total_candidates_analyzed']}")
        doc.add_paragraph(f"Pool Readiness Score: {report['pool_readiness_score']:.1f}%")

        # Critical Gaps
        doc.add_heading("Critical Gaps (≥ 50% Missing)", level=1)
        if report["critical_gaps"]:
            t = doc.add_table(rows=1, cols=4)
            t.style = 'Table Grid'
            hdr = t.rows[0].cells
            hdr[0].text = "Skill"
            hdr[1].text = "Category"
            hdr[2].text = "Missing Count"
            hdr[3].text = "Missing %"
            for g in report["critical_gaps"]:
                r = t.add_row().cells
                r[0].text = str(g["skill"])
                r[1].text = str(g["category"])
                r[2].text = str(g["missing_count"])
                r[3].text = f"{g['missing_percentage']:.1f}%"
        else:
            doc.add_paragraph("No critical skill gaps identified in the candidate pool.")

        # Moderate Gaps
        doc.add_heading("Moderate Gaps (20% – 49% Missing)", level=1)
        if report["moderate_gaps"]:
            t = doc.add_table(rows=1, cols=4)
            t.style = 'Table Grid'
            hdr = t.rows[0].cells
            hdr[0].text = "Skill"
            hdr[1].text = "Category"
            hdr[2].text = "Missing Count"
            hdr[3].text = "Missing %"
            for g in report["moderate_gaps"]:
                r = t.add_row().cells
                r[0].text = str(g["skill"])
                r[1].text = str(g["category"])
                r[2].text = str(g["missing_count"])
                r[3].text = f"{g['missing_percentage']:.1f}%"
        else:
            doc.add_paragraph("No moderate skill gaps identified in the candidate pool.")

        # Minor Gaps
        doc.add_heading("Minor Gaps (< 20% Missing or Nice-to-Have)", level=1)
        if report["minor_gaps"]:
            t = doc.add_table(rows=1, cols=4)
            t.style = 'Table Grid'
            hdr = t.rows[0].cells
            hdr[0].text = "Skill"
            hdr[1].text = "Category"
            hdr[2].text = "Missing Count"
            hdr[3].text = "Missing %"
            for g in report["minor_gaps"]:
                r = t.add_row().cells
                r[0].text = str(g["skill"])
                r[1].text = str(g["category"])
                r[2].text = str(g["missing_count"])
                r[3].text = f"{g['missing_percentage']:.1f}%"
        else:
            doc.add_paragraph("No minor skill gaps identified in the candidate pool.")

        # Well-Covered Skills
        doc.add_heading("Well-Covered Required Skills (≥ 80% Coverage)", level=1)
        if report["well_covered_skills"]:
            t = doc.add_table(rows=1, cols=2)
            t.style = 'Table Grid'
            hdr = t.rows[0].cells
            hdr[0].text = "Skill"
            hdr[1].text = "Coverage %"
            for w in report["well_covered_skills"]:
                r = t.add_row().cells
                r[0].text = str(w["skill"])
                r[1].text = f"{w['coverage_percentage']:.1f}%"
        else:
            doc.add_paragraph("No required skills currently meet the 80% coverage threshold.")

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="skill_gap_report_job_{job_id}.docx"'},
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported format. Choose 'csv' or 'docx'.")


@app.get("/api/jobs/{job_id}/skill-gap-report/candidates/{candidate_id}", response_model=CandidateSkillGap)
def get_candidate_skill_gap(
    job_id: int,
    candidate_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    """
    Get skill gaps for a specific candidate against a specific job posting.
    """
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    candidate = db.query(Candidate).filter(
        Candidate.candidate_id == candidate_id,
        Candidate.deleted_at.is_(None),
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    job_dict = _job_to_dict(job)
    c_dict = _candidate_to_dict(candidate)
    return skill_gap_analysis.analyze_candidate_skill_gap(c_dict, job_dict)


def _build_candidate_development_docx(report: dict) -> "Document":
    doc = Document()
    doc.add_heading("SmartHire AI — Candidate Skill Gap & Development Report", level=0)
    doc.add_paragraph(f"Candidate: {report.get('candidate_name') or 'Unknown Candidate'} (ID: {report['candidate_id']})")
    doc.add_paragraph(f"Job Position: {report['job_title']} (Job ID: {report['job_id']})")
    doc.add_paragraph(f"Generated At: {report['generated_at']}")
    doc.add_paragraph(f"Overall Fit Score: {report['overall_fit_score']:.1f}%  |  Readiness: {report['readiness_level'].replace('_', ' ').title()}")

    doc.add_heading("Matched Skills", level=1)
    if report["matched_required"] or report["matched_nice_to_have"]:
        if report["matched_required"]:
            doc.add_paragraph("Required: " + ", ".join(report["matched_required"]))
        if report["matched_nice_to_have"]:
            doc.add_paragraph("Nice-to-Have: " + ", ".join(report["matched_nice_to_have"]))
    else:
        doc.add_paragraph("No matched skills.")

    for heading, items in [("Missing Required Skills", report["missing_required"]),
                            ("Missing Nice-to-Have Skills", report["missing_nice_to_have"])]:
        doc.add_heading(heading, level=1)
        if items:
            t = doc.add_table(rows=1, cols=3)
            t.style = 'Table Grid'
            hdr = t.rows[0].cells
            hdr[0].text, hdr[1].text, hdr[2].text = "Skill", "Pool Coverage %", "Priority"
            for it in items:
                r = t.add_row().cells
                r[0].text = str(it["skill"])
                r[1].text = f"{it['pool_coverage_percentage']:.1f}%"
                r[2].text = str(it["priority"]).title()
        else:
            doc.add_paragraph("None.")

    doc.add_heading("Development Recommendations", level=1)
    for i, rec in enumerate(report["development_recommendations"], 1):
        doc.add_paragraph(f"{i}. {rec}")
    return doc


@app.get(
    "/api/jobs/{job_id}/skill-gap-report/candidates/{candidate_id}/development-report",
    response_model=CandidateDevelopmentReport,
)
def get_candidate_development_report(
    job_id: int,
    candidate_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    """Richer companion to get_candidate_skill_gap: fit score, readiness,
    matched skills, and pool-relative priority per missing skill."""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    candidate = db.query(Candidate).filter(
        Candidate.candidate_id == candidate_id,
        Candidate.deleted_at.is_(None),
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    job_dict = _job_to_dict(job)
    c_dict = _candidate_to_dict(candidate)
    candidate_pool = _load_candidates_as_dicts(db)
    return skill_gap_analysis.generate_candidate_development_report(c_dict, job_dict, candidate_pool)


@app.get("/api/jobs/{job_id}/skill-gap-report/candidates/{candidate_id}/development-report/export")
def export_candidate_development_report(
    job_id: int,
    candidate_id: int,
    format: Literal["csv", "docx"] = "docx",
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    """Export one candidate's development report as CSV or DOCX."""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    candidate = db.query(Candidate).filter(
        Candidate.candidate_id == candidate_id,
        Candidate.deleted_at.is_(None),
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    job_dict = _job_to_dict(job)
    c_dict = _candidate_to_dict(candidate)
    candidate_pool = _load_candidates_as_dicts(db)
    report = skill_gap_analysis.generate_candidate_development_report(c_dict, job_dict, candidate_pool)

    if format == "csv":
        rows = [{**it, "status": "missing"} for it in report["missing_required"] + report["missing_nice_to_have"]]
        rows += [{"skill": s, "category": "matched", "pool_coverage_percentage": None, "priority": None, "status": "matched"}
                 for s in report["matched_required"] + report["matched_nice_to_have"]]
        df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["skill", "category", "pool_coverage_percentage", "priority", "status"])
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        return StreamingResponse(
            io.BytesIO(csv_bytes), media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="development_report_candidate_{candidate_id}_job_{job_id}.csv"'},
        )
    elif format == "docx":
        doc = _build_candidate_development_docx(report)
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="development_report_candidate_{candidate_id}_job_{job_id}.docx"'},
        )
    raise HTTPException(status_code=400, detail="Unsupported format. Choose 'csv' or 'docx'.")


@app.get("/api/jobs/{job_id}/skill-gap-report/development-reports/batch-export")
def export_batch_candidate_development_reports(
    job_id: int,
    top_n: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    """Zip one DOCX development report per top-N ranked candidate for this
    job. Capped at 50 — each report scans the whole pool, so this loops
    that work top_n times."""
    import zipfile

    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job_dict = _job_to_dict(job)
    candidate_pool = _load_candidates_as_dicts(db)
    ranked = matching_engine.rank_candidates(job_dict, candidate_pool)[:top_n]
    pool_by_id = {c["candidate_id"]: c for c in candidate_pool}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for ranked_c in ranked:
            cid = ranked_c.get("candidate_id")
            c_dict = pool_by_id.get(cid)
            if not c_dict:
                continue
            report = skill_gap_analysis.generate_candidate_development_report(c_dict, job_dict, candidate_pool)
            doc = _build_candidate_development_docx(report)
            doc_buf = io.BytesIO()
            doc.save(doc_buf)
            zf.writestr(f"development_report_candidate_{cid}_job_{job_id}.docx", doc_buf.getvalue())

    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="development_reports_top{top_n}_job_{job_id}.zip"'},
    )



@app.get("/api/jobs/{job_id}/skill-gap-report", response_model=SkillGapReport)
def get_job_skill_gap_report(
    job_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    """
    Generate aggregated skill gap report across candidate pool for a specific job.
    """
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job_dict = _job_to_dict(job)
    candidates = _load_candidates_as_dicts(db)
    report = skill_gap_analysis.analyze_job_skill_gaps(job_dict, candidates)
    return SkillGapReport(**report)


# ---------------------------------------------------------------------------
# Interview Assistant Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/jobs/{job_id}/interview-questions", response_model=InterviewQuestionSet)
def get_interview_questions(
    job_id: int,
    question_type: Literal["Technical", "Behavioral", "Scenario-based"] = "Technical",
    count: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job_dict = _job_to_dict(job)
    try:
        return interview_assistant.generate_interview_questions(job_dict, question_type, count)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/jobs/{job_id}/interview-questions/practice", response_model=PracticeQuestionSet)
def get_practice_questions(
    job_id: int,
    question_type: Literal["Technical", "Behavioral", "Scenario-based"] = "Technical",
    difficulty: Literal["Easy", "Medium", "Hard"] = "Medium",
    question_format: Literal["Open-ended", "Multiple Choice"] = "Open-ended",
    count: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
    _user: User = Depends(require_recruiter),
):
    """Richer sibling of get_interview_questions: adds difficulty and MCQ
    format. Does not replace the existing endpoint."""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job_dict = _job_to_dict(job)
    try:
        return interview_assistant.generate_practice_questions(
            job_dict, question_type, difficulty, question_format, count
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


def _session_to_response(session: "InterviewSession", db: Session) -> dict:
    candidate = db.query(Candidate).filter(Candidate.candidate_id == session.candidate_id).first()
    job = db.query(Job).filter(Job.job_id == session.job_id).first()
    feedback_data = None
    if getattr(session, "feedback", None):
        try:
            feedback_data = json.loads(session.feedback)
        except Exception:
            feedback_data = {"raw": session.feedback}

    return {
        "session_id": session.session_id,
        "candidate_id": session.candidate_id,
        "candidate_name": candidate.name if candidate else None,
        "job_id": session.job_id,
        "job_title": job.title if job else "Unknown Job",
        "status": session.status,
        "transcript": json.loads(session.transcript) if session.transcript else [],
        "feedback": feedback_data,
        "interview_type": getattr(session, "interview_type", "mixed") or "mixed",
        "difficulty": getattr(session, "difficulty", "Medium") or "Medium",
        "scheduled_at": session.scheduled_at.isoformat() if session.scheduled_at else None,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


@app.post("/api/interview-sessions", response_model=InterviewSessionResponse)
def create_interview_session(
    payload: InterviewSessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_recruiter),
):
    """Adds a candidate to the interview pipeline. Pure record-keeping — does
    not call any LLM. (The AI interview simulation feature, if added later,
    drives the transcript forward via its own endpoint on top of this.)"""
    candidate = db.query(Candidate).filter(Candidate.candidate_id == payload.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    job = db.query(Job).filter(Job.job_id == payload.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    scheduled_dt = None
    if payload.scheduled_at:
        try:
            scheduled_dt = datetime.fromisoformat(payload.scheduled_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="scheduled_at must be a valid ISO datetime string")

    session = InterviewSession(
        candidate_id=payload.candidate_id, job_id=payload.job_id,
        status="scheduled" if scheduled_dt else "in_progress",
        transcript="[]", scheduled_at=scheduled_dt, created_by=user.user_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_to_response(session, db)


@app.post("/api/interview-sessions/{session_id}/respond", response_model=InterviewSessionResponse)
def respond_to_interview(
    session_id: int, payload: InterviewCandidateMessage,
    db: Session = Depends(get_db), _user: User = Depends(require_recruiter),
):
    """Drives the AI interviewer forward. Call with no message to generate
    the opening message for a freshly-created session; call with a message
    to submit the candidate's reply and get the next interviewer turn."""
    session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    if session.status == "completed":
        raise HTTPException(status_code=400, detail="This interview session has already been completed")

    candidate = db.query(Candidate).filter(Candidate.candidate_id == session.candidate_id).first()
    job = db.query(Job).filter(Job.job_id == session.job_id).first()
    transcript = json.loads(session.transcript) if session.transcript else []
    if payload.message:
        transcript.append({"role": "candidate", "content": payload.message, "timestamp": datetime.now(timezone.utc).isoformat()})

    job_dict = _job_to_dict(job)
    c_dict = _candidate_to_dict(candidate)
    try:
        reply = interview_assistant.get_interview_response(job_dict, c_dict, transcript)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    transcript.append({"role": "interviewer", "content": reply, "timestamp": datetime.now(timezone.utc).isoformat()})

    session.transcript = json.dumps(transcript)
    session.status = "in_progress"
    db.commit()
    db.refresh(session)
    return _session_to_response(session, db)


@app.post("/api/interview-sessions/{session_id}/complete", response_model=InterviewSessionResponse)
def complete_interview_session(
    session_id: int, db: Session = Depends(get_db), _user: User = Depends(require_recruiter),
):
    session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    session.status = "completed"
    db.commit()
    db.refresh(session)
    return _session_to_response(session, db)


@app.get("/api/interview-sessions", response_model=List[InterviewSessionResponse])
def list_interview_sessions(
    job_id: Optional[int] = None, status: Optional[str] = None,
    db: Session = Depends(get_db), _user: User = Depends(require_recruiter),
):
    """Powers the ATS-style pipeline view with batched candidate/job lookups."""
    query = db.query(InterviewSession)
    if job_id is not None:
        query = query.filter(InterviewSession.job_id == job_id)
    if status is not None:
        query = query.filter(InterviewSession.status == status)
    sessions = query.order_by(InterviewSession.updated_at.desc()).all()
    if not sessions:
        return []

    cand_ids = {s.candidate_id for s in sessions if s.candidate_id is not None}
    job_ids = {s.job_id for s in sessions if s.job_id is not None}
    cand_map = {
        c.candidate_id: c.name
        for c in db.query(Candidate.candidate_id, Candidate.name).filter(Candidate.candidate_id.in_(cand_ids)).all()
    } if cand_ids else {}
    job_map = {
        j.job_id: j.title
        for j in db.query(Job.job_id, Job.title).filter(Job.job_id.in_(job_ids)).all()
    } if job_ids else {}

    results = []
    for s in sessions:
        results.append({
            "session_id": s.session_id,
            "candidate_id": s.candidate_id,
            "candidate_name": cand_map.get(s.candidate_id),
            "job_id": s.job_id,
            "job_title": job_map.get(s.job_id) or "Unknown Job",
            "status": s.status,
            "transcript": json.loads(s.transcript) if s.transcript else [],
            "feedback": json.loads(s.feedback) if getattr(s, "feedback", None) else None,
            "interview_type": getattr(s, "interview_type", "mixed") or "mixed",
            "difficulty": getattr(s, "difficulty", "Medium") or "Medium",
            "scheduled_at": s.scheduled_at.isoformat() if s.scheduled_at else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        })
    return results


@app.get("/api/interview-sessions/{session_id}", response_model=InterviewSessionResponse)
def get_interview_session(
    session_id: int, db: Session = Depends(get_db), _user: User = Depends(require_recruiter),
):
    session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    return _session_to_response(session, db)


# ---------------------------------------------------------------------------
# Candidate Portal Endpoints
# ---------------------------------------------------------------------------

def _get_or_create_candidate_for_user(user: User, db: Session) -> Candidate:
    cand = db.query(Candidate).filter(Candidate.user_id == user.user_id).first()
    if not cand:
        cand = db.query(Candidate).filter(Candidate.email == user.email, Candidate.user_id == None).first()
        if cand:
            cand.user_id = user.user_id
            db.commit()
            db.refresh(cand)
        else:
            cand = Candidate(
                user_id=user.user_id,
                name=user.full_name,
                email=user.email,
                phone=user.phone_number,
                education="[]",
                skills="[]",
                experience="[]",
                certifications="[]",
                projects="[]",
            )
            db.add(cand)
            db.commit()
            db.refresh(cand)
    return cand


def _candidate_to_profile_response(cand: Optional[Candidate], user: User) -> dict:
    def _parse(field):
        if not field:
            return []
        if isinstance(field, list):
            return field
        try:
            val = json.loads(field)
            return val if isinstance(val, list) else []
        except Exception:
            return []

    return {
        "user_id": user.user_id,
        "candidate_id": cand.candidate_id if cand else None,
        "name": cand.name if cand and cand.name else user.full_name,
        "email": cand.email if cand and cand.email else user.email,
        "phone": cand.phone if cand and cand.phone else user.phone_number,
        "education": _parse(cand.education) if cand else [],
        "skills": _parse(cand.skills) if cand else [],
        "experience": _parse(cand.experience) if cand else [],
        "certifications": _parse(cand.certifications) if cand else [],
        "projects": _parse(cand.projects) if cand else [],
        "resume_path": cand.resume_path if cand else None,
        "stage": cand.stage if cand else None,
        "created_at": cand.created_at if cand else user.created_at,
    }


@app.get("/api/candidate/jobs", response_model=List[JobResponse])
def get_candidate_jobs(
    db: Session = Depends(get_db),
    _user: User = Depends(require_candidate),
):
    jobs = db.query(Job).filter(Job.status == "open").order_by(Job.created_at.desc()).all()
    return [JobResponse.from_orm_model(j) for j in jobs]


@app.get("/api/candidate/profile", response_model=CandidateProfileResponse)
def get_candidate_profile(
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    cand = db.query(Candidate).filter(Candidate.user_id == user.user_id).first()
    return _candidate_to_profile_response(cand, user)


@app.put("/api/candidate/profile", response_model=CandidateProfileResponse)
def update_candidate_profile(
    payload: CandidateProfileUpdate,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    cand = _get_or_create_candidate_for_user(user, db)
    if payload.name is not None:
        cand.name = payload.name
    if payload.email is not None:
        cand.email = payload.email
    if payload.phone is not None:
        cand.phone = payload.phone
    if payload.education is not None:
        cand.education = json.dumps(payload.education)
    if payload.skills is not None:
        cand.skills = json.dumps(payload.skills)
    if payload.experience is not None:
        cand.experience = json.dumps(payload.experience)
    if payload.certifications is not None:
        cand.certifications = json.dumps(payload.certifications)
    if payload.projects is not None:
        cand.projects = json.dumps(payload.projects)

    db.commit()
    db.refresh(cand)
    return _candidate_to_profile_response(cand, user)


@app.post("/api/candidate/resume/upload", response_model=CandidateProfileResponse)
async def upload_candidate_resume(
    file: UploadFile = File(...),
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    if settings_store.get_setting(db, "feature_resume_ai") == "false":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The AI Resume Intelligence feature is currently disabled by an administrator.",
        )
    filename = os.path.basename(file.filename or "resume.pdf")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".pdf", ".docx", ".txt"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload a .pdf, .docx, or .txt resume.",
        )

    os.makedirs("uploads", exist_ok=True)
    saved_filename = f"user_{user.user_id}_{filename}"
    file_path = os.path.join("uploads", saved_filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        raw_text = file_loader.extract_text(file_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to extract text from file: {e}")

    extracted = parser.extract_candidate_info(raw_text)

    cand = _get_or_create_candidate_for_user(user, db)
    if extracted.get("name") and extracted["name"] != "Unknown Candidate":
        cand.name = extracted["name"]
    if extracted.get("email"):
        cand.email = extracted["email"]
    if extracted.get("phone"):
        cand.phone = extracted["phone"]
    if extracted.get("education"):
        cand.education = json.dumps(extracted["education"])
    if extracted.get("skills"):
        cand.skills = json.dumps(extracted["skills"])
    if extracted.get("experience"):
        cand.experience = json.dumps(extracted["experience"])
    if extracted.get("certifications"):
        cand.certifications = json.dumps(extracted["certifications"])
    if extracted.get("projects"):
        cand.projects = json.dumps(extracted["projects"])
    cand.resume_path = saved_filename

    db.commit()
    db.refresh(cand)
    return _candidate_to_profile_response(cand, user)


@app.post("/api/candidate/resume/analyze", response_model=ResumeAnalysisResponse)
def analyze_candidate_resume(
    payload: Optional[ResumeAnalysisRequest] = None,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    if settings_store.get_setting(db, "feature_resume_ai") == "false":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The AI Resume Intelligence feature is currently disabled by an administrator.",
        )
    cand = _get_or_create_candidate_for_user(user, db)
    c_dict = _candidate_to_dict(cand)

    target_job_dict = None
    target_job_id = payload.target_job_id if payload else None
    target_job_title = None

    if target_job_id:
        job = db.query(Job).filter(Job.job_id == target_job_id).first()
        if job:
            target_job_dict = _job_to_dict(job)
            target_job_title = job.title

    try:
        analysis = candidate_service.generate_resume_analysis(c_dict, target_job_dict)
    except Exception as e:
        logger.warning("Resume analysis failed: %s", e)
        raise HTTPException(status_code=502, detail=f"AI service failure during resume analysis: {e}")

    record = ResumeAnalysis(
        user_id=user.user_id,
        candidate_id=cand.candidate_id,
        target_job_id=target_job_id,
        analysis_data=json.dumps(analysis),
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "analysis_id": record.analysis_id,
        "user_id": record.user_id,
        "candidate_id": record.candidate_id,
        "target_job_id": record.target_job_id,
        "target_job_title": target_job_title,
        "analysis": analysis,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@app.get("/api/candidate/resume/analysis", response_model=ResumeAnalysisResponse)
def get_candidate_resume_analysis(
    target_job_id: Optional[int] = None,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    query = db.query(ResumeAnalysis).filter(ResumeAnalysis.user_id == user.user_id)
    if target_job_id is not None:
        query = query.filter(ResumeAnalysis.target_job_id == target_job_id)
    record = query.order_by(ResumeAnalysis.created_at.desc()).first()

    if not record:
        req = ResumeAnalysisRequest(target_job_id=target_job_id)
        return analyze_candidate_resume(req, user=user, db=db)

    job_title = None
    if record.target_job_id:
        job = db.query(Job).filter(Job.job_id == record.target_job_id).first()
        if job:
            job_title = job.title

    return {
        "analysis_id": record.analysis_id,
        "user_id": record.user_id,
        "candidate_id": record.candidate_id,
        "target_job_id": record.target_job_id,
        "target_job_title": job_title,
        "analysis": json.loads(record.analysis_data),
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@app.get("/api/candidate/practice-questions", response_model=PracticeQuestionSet)
def get_candidate_practice_questions(
    job_id: Optional[int] = None,
    question_type: Literal["Technical", "Behavioral", "Scenario-based"] = "Technical",
    difficulty: Literal["Easy", "Medium", "Hard"] = "Medium",
    question_format: Literal["Open-ended", "Multiple Choice"] = "Open-ended",
    count: int = Query(3, ge=1, le=10),
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    if settings_store.get_setting(db, "feature_practice") == "false":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The Practice Assessment feature is currently disabled by an administrator.",
        )
    if job_id:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job_dict = _job_to_dict(job)
    else:
        cand = _get_or_create_candidate_for_user(user, db)
        skills = json.loads(cand.skills) if cand.skills else []
        job_dict = {
            "job_id": 0,
            "title": "Software Engineering Candidate",
            "seniority": "Mid-Level",
            "min_experience_years": 2,
            "required_skills": skills[:5] if skills else ["Python", "SQL", "Git"],
            "nice_to_have_skills": [],
            "description": "Practice interview questions for technical candidates.",
        }

    try:
        return interview_assistant.generate_practice_questions(
            job_dict, question_type, difficulty, question_format, count
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/candidate/practice-answers", response_model=PracticeAnswerResponse)
def submit_candidate_practice_answer(
    payload: PracticeAnswerSubmit,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    if settings_store.get_setting(db, "feature_practice") == "false":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The Practice Assessment feature is currently disabled by an administrator.",
        )
    cand = _get_or_create_candidate_for_user(user, db)
    job_title = "Software Engineer"
    if payload.job_id:
        job = db.query(Job).filter(Job.job_id == payload.job_id).first()
        if job:
            job_title = job.title

    try:
        feedback = candidate_service.evaluate_practice_answer(
            question_text=payload.question_text,
            candidate_answer=payload.candidate_answer,
            question_type=payload.question_type or "Technical",
            difficulty=payload.difficulty or "Medium",
            job_title=job_title,
        )
    except Exception as e:
        logger.warning("Practice answer evaluation failed: %s", e)
        raise HTTPException(status_code=502, detail=f"AI service failure during practice evaluation: {e}")

    record = PracticeAnswer(
        user_id=user.user_id,
        candidate_id=cand.candidate_id,
        job_id=payload.job_id,
        question_text=payload.question_text,
        question_type=payload.question_type or "Technical",
        difficulty=payload.difficulty or "Medium",
        candidate_answer=payload.candidate_answer,
        feedback=json.dumps(feedback),
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "answer_id": record.answer_id,
        "user_id": record.user_id,
        "candidate_id": record.candidate_id,
        "job_id": record.job_id,
        "job_title": job_title,
        "question_text": record.question_text,
        "question_type": record.question_type,
        "difficulty": record.difficulty,
        "candidate_answer": record.candidate_answer,
        "feedback": feedback,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@app.get("/api/candidate/practice-history", response_model=List[PracticeAnswerResponse])
def get_candidate_practice_history(
    job_id: Optional[int] = None,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    query = db.query(PracticeAnswer).filter(PracticeAnswer.user_id == user.user_id)
    if job_id is not None:
        query = query.filter(PracticeAnswer.job_id == job_id)
    records = query.order_by(PracticeAnswer.created_at.desc()).all()

    job_ids = {r.job_id for r in records if r.job_id}
    job_map = {j.job_id: j.title for j in db.query(Job.job_id, Job.title).filter(Job.job_id.in_(job_ids)).all()} if job_ids else {}

    results = []
    for r in records:
        try:
            fb = json.loads(r.feedback)
        except Exception:
            fb = {}
        results.append({
            "answer_id": r.answer_id,
            "user_id": r.user_id,
            "candidate_id": r.candidate_id,
            "job_id": r.job_id,
            "job_title": job_map.get(r.job_id) or "General Practice",
            "question_text": r.question_text,
            "question_type": r.question_type,
            "difficulty": r.difficulty,
            "candidate_answer": r.candidate_answer,
            "feedback": fb,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return results


@app.post("/api/candidate/mock-interview/start", response_model=InterviewSessionResponse)
def start_candidate_mock_interview(
    payload: CandidateMockInterviewStart,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    if settings_store.get_setting(db, "feature_mock_interview") == "false":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The AI Mock Interview feature is currently disabled by an administrator.",
        )
    job = db.query(Job).filter(Job.job_id == payload.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    cand = _get_or_create_candidate_for_user(user, db)

    session = InterviewSession(
        candidate_id=cand.candidate_id,
        job_id=payload.job_id,
        status="in_progress",
        transcript="[]",
        interview_type=payload.interview_type or "mixed",
        difficulty=payload.difficulty or "Medium",
        created_by=user.user_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    job_dict = _job_to_dict(job)
    c_dict = _candidate_to_dict(cand)
    try:
        opening = interview_assistant.get_interview_response(job_dict, c_dict, [])
    except Exception:
        opening = f"Hello {cand.name or 'there'}, welcome to your interview for the {job.title} role! To begin, could you tell me a little about your technical background and what brings you to this role?"

    transcript = [{"role": "interviewer", "content": opening, "timestamp": datetime.now(timezone.utc).isoformat()}]
    session.transcript = json.dumps(transcript)
    db.commit()
    db.refresh(session)

    return _session_to_response(session, db)


@app.post("/api/candidate/mock-interview/{session_id}/respond", response_model=InterviewSessionResponse)
def respond_candidate_mock_interview(
    session_id: int,
    payload: InterviewCandidateMessage,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    if settings_store.get_setting(db, "feature_mock_interview") == "false":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The AI Mock Interview feature is currently disabled by an administrator.",
        )
    session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    if session.created_by != user.user_id:
        cand = db.query(Candidate).filter(Candidate.candidate_id == session.candidate_id).first()
        if not cand or cand.user_id != user.user_id:
            raise HTTPException(status_code=403, detail="Not authorized to access this interview session")

    if session.status == "completed":
        raise HTTPException(status_code=400, detail="This interview session has already been completed")

    candidate = db.query(Candidate).filter(Candidate.candidate_id == session.candidate_id).first()
    job = db.query(Job).filter(Job.job_id == session.job_id).first()
    transcript = json.loads(session.transcript) if session.transcript else []

    if payload.message:
        transcript.append({"role": "candidate", "content": payload.message, "timestamp": datetime.now(timezone.utc).isoformat()})

    job_dict = _job_to_dict(job)
    c_dict = _candidate_to_dict(candidate)
    try:
        reply = interview_assistant.get_interview_response(job_dict, c_dict, transcript)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    transcript.append({"role": "interviewer", "content": reply, "timestamp": datetime.now(timezone.utc).isoformat()})

    session.transcript = json.dumps(transcript)
    session.status = "in_progress"
    db.commit()
    db.refresh(session)
    return _session_to_response(session, db)


@app.post("/api/candidate/mock-interview/{session_id}/complete", response_model=InterviewSessionResponse)
def complete_candidate_mock_interview(
    session_id: int,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    if session.created_by != user.user_id:
        cand = db.query(Candidate).filter(Candidate.candidate_id == session.candidate_id).first()
        if not cand or cand.user_id != user.user_id:
            raise HTTPException(status_code=403, detail="Not authorized to access this interview session")

    candidate = db.query(Candidate).filter(Candidate.candidate_id == session.candidate_id).first()
    job = db.query(Job).filter(Job.job_id == session.job_id).first()
    transcript = json.loads(session.transcript) if session.transcript else []

    job_dict = _job_to_dict(job)
    c_dict = _candidate_to_dict(candidate)

    try:
        evaluation = candidate_service.evaluate_mock_interview(job_dict, c_dict, transcript)
    except Exception as e:
        logger.warning("Mock interview evaluation failed: %s", e)
        raise HTTPException(status_code=502, detail=f"AI service failure during mock interview evaluation: {e}")

    session.status = "completed"
    session.feedback = json.dumps(evaluation)
    db.commit()
    db.refresh(session)
    return _session_to_response(session, db)


@app.get("/api/candidate/mock-interviews", response_model=List[InterviewSessionResponse])
def list_candidate_mock_interviews(
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    cand = db.query(Candidate).filter(Candidate.user_id == user.user_id).first()
    user_cand_id = cand.candidate_id if cand else -1

    sessions = (
        db.query(InterviewSession)
        .filter(or_(InterviewSession.created_by == user.user_id, InterviewSession.candidate_id == user_cand_id))
        .order_by(InterviewSession.updated_at.desc())
        .all()
    )
    return [_session_to_response(s, db) for s in sessions]


@app.get("/api/candidate/mock-interviews/{session_id}", response_model=InterviewSessionResponse)
def get_candidate_mock_interview(
    session_id: int,
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    if session.created_by != user.user_id:
        cand = db.query(Candidate).filter(Candidate.candidate_id == session.candidate_id).first()
        if not cand or cand.user_id != user.user_id:
            raise HTTPException(status_code=403, detail="Not authorized to access this interview session")
    return _session_to_response(session, db)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
