import json
import re
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


# ---------------------------------------------------------------------------
# Candidate schemas (unchanged from Milestone 1)
# ---------------------------------------------------------------------------

class CandidateCreate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    education: Optional[List[Any]] = None
    skills: Optional[List[str]] = None
    experience: Optional[List[Any]] = None
    certifications: Optional[List[Any]] = None
    projects: Optional[List[Any]] = None
    resume_path: Optional[str] = None


class CandidateResponse(BaseModel):
    candidate_id: int
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    education: Optional[List[Any]] = None
    skills: Optional[List[str]] = None
    experience: Optional[List[Any]] = None
    certifications: Optional[List[Any]] = None
    projects: Optional[List[Any]] = None
    resume_path: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_model(cls, db_obj):
        def parse_json(field):
            if not field:
                return []
            try:
                return json.loads(field)
            except Exception:
                return []

        return cls(
            candidate_id=db_obj.candidate_id,
            name=db_obj.name,
            email=db_obj.email,
            phone=db_obj.phone,
            education=parse_json(db_obj.education),
            skills=parse_json(db_obj.skills),
            experience=parse_json(db_obj.experience),
            certifications=parse_json(db_obj.certifications),
            projects=parse_json(db_obj.projects),
            resume_path=db_obj.resume_path,
            created_at=db_obj.created_at
        )


class CandidateListResponse(BaseModel):
    total: int
    candidates: List[CandidateResponse]


class SkillFrequency(BaseModel):
    skill: str
    count: int


class MatchResult(BaseModel):
    candidate_name: Optional[str] = None
    email: Optional[str] = None
    match_score: float
    matched_skills: List[str]
    missing_skills: List[str]
    source_file: Optional[str] = None


# ---------------------------------------------------------------------------
# Auth / User schemas
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ALLOWED_ROLES = {"Recruiter", "HR Manager", "Admin"}


class UserCreate(BaseModel):
    """Input schema for registration.  password_hash is never accepted here."""
    full_name: str
    email: str
    password: str
    confirm_password: str
    company_name: str
    job_title: str          # "Recruiter" | "HR Manager" | "Admin"
    phone_number: Optional[str] = None

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address format.")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v

    @field_validator("job_title")
    @classmethod
    def role_valid(cls, v: str) -> str:
        if v not in _ALLOWED_ROLES:
            raise ValueError(f"job_title must be one of: {', '.join(_ALLOWED_ROLES)}")
        return v

    @field_validator("full_name", "company_name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("This field cannot be empty.")
        return v.strip()

    @model_validator(mode="after")
    def passwords_match(self) -> "UserCreate":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    """Returned to the client — password_hash is intentionally absent."""
    user_id: int
    full_name: str
    email: str
    company_name: str
    job_title: str
    phone_number: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_model(cls, db_obj) -> "UserResponse":
        return cls(
            user_id=db_obj.user_id,
            full_name=db_obj.full_name,
            email=db_obj.email,
            company_name=db_obj.company_name,
            job_title=db_obj.job_title,
            phone_number=db_obj.phone_number,
            is_active=db_obj.is_active,
            created_at=db_obj.created_at,
        )


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
