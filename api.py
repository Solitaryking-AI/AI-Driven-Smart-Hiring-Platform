import os
import io
import json
import uvicorn
from collections import Counter
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import List, Optional, Literal

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
from models import Candidate, User, Job, InterviewSession, ResumeAnalysis, PracticeAnswer
from schemas import (
    CandidateCreate, CandidateResponse, CandidateListResponse,
    SkillFrequency, AnalyticsSummary, MatchResult, MatchBreakdown, HiringScoreBreakdown,
    SkillGapItem, WellCoveredSkill, SkillGapReport, CandidateSkillGap, CandidateDevelopmentReport,
    InterviewQuestionSet, PracticeQuestionSet, InterviewMessage, InterviewSessionResponse, InterviewSessionCreate,
    InterviewCandidateMessage,
    JobCreate, JobUpdate, JobResponse,
    UserCreate, UserLogin, UserResponse, Token,
    CandidateProfileUpdate, CandidateProfileResponse,
    ResumeAnalysisRequest, ResumeAnalysisResponse,
    PracticeAnswerSubmit, PracticeAnswerResponse,
    CandidateMockInterviewStart,
)
from auth import hash_password, verify_password, create_access_token, decode_access_token
from services import matching_engine, hiring_score, skill_gap_analysis, interview_assistant, candidate_service
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Decode the Bearer JWT and return the corresponding User row.
    Raises 401 if the token is missing, expired, or invalid.
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

    return user


# ---------------------------------------------------------------------------
# Auth endpoints  (public — no authentication required)
# ---------------------------------------------------------------------------

@app.post("/api/auth/register", response_model=Token, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    # Duplicate-email check
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    db_user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        company_name=payload.company_name,
        job_title=payload.job_title,
        phone_number=payload.phone_number,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    token = create_access_token({"sub": db_user.email})
    return Token(access_token=token, user=UserResponse.from_orm_model(db_user))


@app.post("/api/auth/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    ident = payload.email.strip()
    ident_lower = ident.lower()

    # 1. Primary lookup by exact email match
    exact_user = db.query(User).filter(func.lower(User.email) == ident_lower).first()
    if exact_user and verify_password(payload.password, exact_user.password_hash):
        if not exact_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is disabled. Contact your administrator.",
            )
        token = create_access_token({"sub": exact_user.email})
        return Token(access_token=token, user=UserResponse.from_orm_model(exact_user))

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
            if not u.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your account is disabled. Contact your administrator.",
                )
            token = create_access_token({"sub": u.email})
            return Token(access_token=token, user=UserResponse.from_orm_model(u))

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.from_orm_model(current_user)


# ---------------------------------------------------------------------------
# Candidate endpoints  (all protected — require valid JWT)
# ---------------------------------------------------------------------------

@app.post("/api/candidates/upload", response_model=CandidateResponse)
async def upload_candidate(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    file_path = os.path.join("uploads", file.filename)
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
        db_candidate = db.query(Candidate).filter(Candidate.email == email_val).first()
    if not db_candidate:
        db_candidate = db.query(Candidate).filter(Candidate.resume_path == file.filename).first()

    if db_candidate:
        db_candidate.name = parsed_data.get("name") or db_candidate.name
        db_candidate.email = email_val or db_candidate.email
        db_candidate.phone = parsed_data.get("phone") or db_candidate.phone
        db_candidate.education = json.dumps(parsed_data.get("education", []))
        db_candidate.skills = json.dumps(parsed_data.get("skills", []))
        db_candidate.experience = json.dumps(parsed_data.get("experience", []))
        db_candidate.certifications = json.dumps(parsed_data.get("certifications", []))
        db_candidate.projects = json.dumps(parsed_data.get("projects", []))
        db_candidate.resume_path = file.filename
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
            resume_path=file.filename,
        )
        db.add(db_candidate)

    db.commit()
    db.refresh(db_candidate)
    return CandidateResponse.from_orm_model(db_candidate)


@app.get("/api/candidates", response_model=CandidateListResponse)
def get_candidates(
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(100, ge=1, le=50000),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = db.query(Candidate)
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
    }


def _load_candidates_as_dicts(db: Session) -> List[dict]:
    """Helper to load all Candidate rows into deserialized dictionaries."""
    candidates = db.query(Candidate).all()
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


@app.get("/api/candidates/hiring-scores", response_model=List[HiringScoreBreakdown])
def get_candidates_hiring_scores(
    job_id: Optional[int] = None,
    skip: int = 0,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
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
    _user: User = Depends(get_current_user),
):
    """
    Compute and return the detailed job-independent Hiring Score breakdown for a single candidate.
    """
    candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()
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
    _user: User = Depends(get_current_user),
):
    candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return CandidateResponse.from_orm_model(candidate)


@app.delete("/api/candidates/{candidate_id}")
def delete_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    db.delete(candidate)
    db.commit()
    return {"message": "Candidate deleted successfully"}


@app.delete("/api/candidates")
def delete_all_candidates(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    count = db.query(Candidate).delete()
    db.commit()
    return {"deleted": count}


def _compute_skill_stats(db: Session):
    """Shared helper: scan every Candidate and return aggregate skill data.

    Returns:
        (candidates_total, resumes_parsed, all_skills, counts)
        - candidates_total: number of Candidate rows
        - resumes_parsed: candidates that have at least one parseable skill
        - all_skills: flat list of every normalised skill token (with repeats)
        - counts: Counter mapping each unique skill -> occurrence count
    """
    candidates = db.query(Candidate).all()
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
    _user: User = Depends(get_current_user),
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
    _user: User = Depends(get_current_user),
):
    _total, _parsed, _all, counts = _compute_skill_stats(db)
    return [SkillFrequency(skill=skill.title(), count=count) for skill, count in counts.most_common()]



# ---------------------------------------------------------------------------
# Job Management Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/jobs", response_model=JobResponse, status_code=201)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
        status=payload.status or "open",
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
    _user: User = Depends(get_current_user),
):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    jobs = query.order_by(Job.created_at.desc()).all()
    return [JobResponse.from_orm_model(j) for j in jobs]


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
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
    _user: User = Depends(get_current_user),
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
        job.status = payload.status

    db.commit()
    db.refresh(job)
    return JobResponse.from_orm_model(job)


@app.delete("/api/jobs/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
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
    _user: User = Depends(get_current_user),
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
    _user: User = Depends(get_current_user),
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
    _user: User = Depends(get_current_user),
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
    _user: User = Depends(get_current_user),
):
    """
    Get skill gaps for a specific candidate against a specific job posting.
    """
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()
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
    _user: User = Depends(get_current_user),
):
    """Richer companion to get_candidate_skill_gap: fit score, readiness,
    matched skills, and pool-relative priority per missing skill."""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()
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
    _user: User = Depends(get_current_user),
):
    """Export one candidate's development report as CSV or DOCX."""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()
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
    _user: User = Depends(get_current_user),
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
    _user: User = Depends(get_current_user),
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
    _user: User = Depends(get_current_user),
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
    _user: User = Depends(get_current_user),
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
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


@app.post("/api/interview-sessions", response_model=InterviewSessionResponse)
def create_interview_session(
    payload: InterviewSessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
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
    db: Session = Depends(get_db), _user: User = Depends(get_current_user),
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
    session_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user),
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
    db: Session = Depends(get_db), _user: User = Depends(get_current_user),
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
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        })
    return results


@app.get("/api/interview-sessions/{session_id}", response_model=InterviewSessionResponse)
def get_interview_session(
    session_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user),
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


@app.get("/api/candidate/profile", response_model=CandidateProfileResponse)
def get_candidate_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cand = db.query(Candidate).filter(Candidate.user_id == user.user_id).first()
    return _candidate_to_profile_response(cand, user)


@app.put("/api/candidate/profile", response_model=CandidateProfileResponse)
def update_candidate_profile(
    payload: CandidateProfileUpdate,
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filename = file.filename or "resume.pdf"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".pdf", ".docx", ".txt"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload a .pdf, .docx, or .txt resume.",
        )

    os.makedirs("uploads", exist_ok=True)
    file_path = os.path.join("uploads", f"user_{user.user_id}_{filename}")
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
    cand.resume_path = filename

    db.commit()
    db.refresh(cand)
    return _candidate_to_profile_response(cand, user)


@app.post("/api/candidate/resume/analyze", response_model=ResumeAnalysisResponse)
def analyze_candidate_resume(
    payload: Optional[ResumeAnalysisRequest] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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

    analysis = candidate_service.generate_resume_analysis(c_dict, target_job_dict)

    record = ResumeAnalysis(
        user_id=user.user_id,
        candidate_id=cand.candidate_id,
        target_job_id=target_job_id,
        analysis_data=json.dumps(analysis),
        created_at=datetime.utcnow(),
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
        "created_at": record.created_at.isoformat(),
    }


@app.get("/api/candidate/resume/analysis", response_model=ResumeAnalysisResponse)
def get_candidate_resume_analysis(
    target_job_id: Optional[int] = None,
    user: User = Depends(get_current_user),
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
        "created_at": record.created_at.isoformat(),
    }


@app.get("/api/candidate/practice-questions", response_model=PracticeQuestionSet)
def get_candidate_practice_questions(
    job_id: Optional[int] = None,
    question_type: Literal["Technical", "Behavioral", "Scenario-based"] = "Technical",
    difficulty: Literal["Easy", "Medium", "Hard"] = "Medium",
    question_format: Literal["Open-ended", "Multiple Choice"] = "Open-ended",
    count: int = Query(3, ge=1, le=10),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cand = _get_or_create_candidate_for_user(user, db)
    job_title = "Software Engineer"
    if payload.job_id:
        job = db.query(Job).filter(Job.job_id == payload.job_id).first()
        if job:
            job_title = job.title

    feedback = candidate_service.evaluate_practice_answer(
        question_text=payload.question_text,
        candidate_answer=payload.candidate_answer,
        question_type=payload.question_type or "Technical",
        difficulty=payload.difficulty or "Medium",
        job_title=job_title,
    )

    record = PracticeAnswer(
        user_id=user.user_id,
        candidate_id=cand.candidate_id,
        job_id=payload.job_id,
        question_text=payload.question_text,
        question_type=payload.question_type or "Technical",
        difficulty=payload.difficulty or "Medium",
        candidate_answer=payload.candidate_answer,
        feedback=json.dumps(feedback),
        created_at=datetime.utcnow(),
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
        "created_at": record.created_at.isoformat(),
    }


@app.get("/api/candidate/practice-history", response_model=List[PracticeAnswerResponse])
def get_candidate_practice_history(
    job_id: Optional[int] = None,
    user: User = Depends(get_current_user),
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
            "created_at": r.created_at.isoformat(),
        })
    return results


@app.post("/api/candidate/mock-interview/start", response_model=InterviewSessionResponse)
def start_candidate_mock_interview(
    payload: CandidateMockInterviewStart,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
        created_at=datetime.utcnow(),
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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    user: User = Depends(get_current_user),
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

    evaluation = candidate_service.evaluate_mock_interview(job_dict, c_dict, transcript)

    session.status = "completed"
    session.feedback = json.dumps(evaluation)
    db.commit()
    db.refresh(session)
    return _session_to_response(session, db)


@app.get("/api/candidate/mock-interviews", response_model=List[InterviewSessionResponse])
def list_candidate_mock_interviews(
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
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
