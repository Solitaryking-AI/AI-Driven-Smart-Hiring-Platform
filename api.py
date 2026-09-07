import os
import json
import uvicorn
from collections import Counter
from typing import List, Optional

from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel, ValidationError

from database import engine, get_db, init_db
from models import Candidate, User
from schemas import (
    CandidateCreate, CandidateResponse, CandidateListResponse,
    SkillFrequency, MatchResult,
    UserCreate, UserLogin, UserResponse, Token,
)
from auth import hash_password, verify_password, create_access_token, decode_access_token
import file_loader
import parser

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(title="SmartHire AI Recruitment Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@app.on_event("startup")
def on_startup():
    init_db()
    os.makedirs("uploads", exist_ok=True)


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
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is disabled. Contact your administrator.",
        )

    token = create_access_token({"sub": user.email})
    return Token(access_token=token, user=UserResponse.from_orm_model(user))


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

    db_candidate = db.query(Candidate).filter(Candidate.resume_path == file.filename).first()

    if db_candidate:
        db_candidate.name = parsed_data.get("name")
        db_candidate.email = parsed_data.get("email")
        db_candidate.phone = parsed_data.get("phone")
        db_candidate.education = json.dumps(parsed_data.get("education", []))
        db_candidate.skills = json.dumps(parsed_data.get("skills", []))
        db_candidate.experience = json.dumps(parsed_data.get("experience", []))
        db_candidate.certifications = json.dumps(parsed_data.get("certifications", []))
        db_candidate.projects = json.dumps(parsed_data.get("projects", []))
    else:
        db_candidate = Candidate(
            name=parsed_data.get("name"),
            email=parsed_data.get("email"),
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
    limit: int = 100,
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


@app.get("/api/analytics/skills", response_model=List[SkillFrequency])
def get_skills_analytics(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    candidates = db.query(Candidate).all()
    all_skills = []
    for candidate in candidates:
        if candidate.skills:
            try:
                skills = json.loads(candidate.skills)
                all_skills.extend([s.strip().lower() for s in skills if isinstance(s, str)])
            except Exception:
                pass
    counts = Counter(all_skills)
    return [SkillFrequency(skill=skill.title(), count=count) for skill, count in counts.most_common()]


class MatchRequest(BaseModel):
    required_skills: str


@app.post("/api/match", response_model=List[MatchResult])
def match_candidates(
    req: MatchRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    required_skills_list = [s.strip().lower() for s in req.required_skills.split(",")]
    if not required_skills_list:
        return []

    candidates = db.query(Candidate).all()
    results = []
    for candidate in candidates:
        candidate_skills = []
        if candidate.skills:
            try:
                raw_skills = json.loads(candidate.skills)
                candidate_skills = [s.strip().lower() for s in raw_skills if isinstance(s, str)]
            except Exception:
                pass

        matched, missing = [], []
        for req_skill in required_skills_list:
            if any(req_skill in cs for cs in candidate_skills) or any(cs in req_skill for cs in candidate_skills):
                matched.append(req_skill)
            else:
                missing.append(req_skill)

        score = (len(matched) / len(required_skills_list)) * 100 if required_skills_list else 0
        results.append(MatchResult(
            candidate_name=candidate.name,
            email=candidate.email,
            match_score=round(score, 2),
            matched_skills=[s.title() for s in matched],
            missing_skills=[s.title() for s in missing],
            source_file=candidate.resume_path,
        ))

    results.sort(key=lambda x: x.match_score, reverse=True)
    return results


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
