import json
import re
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


# ---------------------------------------------------------------------------
# Candidate schemas
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


class AnalyticsSummary(BaseModel):
    """Dashboard-wide aggregate stats computed over the FULL candidate pool
    (independent of any list pagination). Powers the top summary stat row."""
    total_candidates: int
    unique_skills: int
    total_skill_occurrences: int
    avg_skills_per_candidate: float
    resumes_parsed: int


class MatchResult(BaseModel):
    """Legacy flat match result schema preserved for backward compatibility."""
    candidate_name: Optional[str] = None
    email: Optional[str] = None
    match_score: float
    matched_skills: List[str]
    missing_skills: List[str]
    source_file: Optional[str] = None


class MatchBreakdown(BaseModel):
    """Detailed multi-factor match result returned by the matching engine."""
    candidate_id: Optional[int] = None
    candidate_name: Optional[str] = None
    email: Optional[str] = None
    final_score: float
    skills_score: float = 0.0
    nice_to_have_score: float = 0.0
    experience_fit_score: float = 0.0
    seniority_score: float = 0.0
    matched_required: List[str] = []
    missing_required: List[str] = []
    matched_nice_to_have: List[str] = []
    missing_nice_to_have: List[str] = []
    candidate_experience_years: Optional[float] = None
    source_file: Optional[str] = None


class HiringScoreBreakdown(BaseModel):
    """Job-independent hiring quality evaluation breakdown for a candidate."""
    candidate_id: Optional[int] = None
    candidate_name: Optional[str] = None
    email: Optional[str] = None
    hiring_score: float
    resume_completeness_score: float = 0.0
    skill_breadth_score: float = 0.0
    experience_stability_score: float = 0.0
    education_level_score: float = 0.0
    certification_score: float = 0.0
    source_file: Optional[str] = None
    blended_score: Optional[float] = None


# ---------------------------------------------------------------------------
# Skill Gap Analysis schemas
# ---------------------------------------------------------------------------

class SkillGapItem(BaseModel):
    """Skill gap entry indicating missing frequency and severity level."""
    skill: str
    category: str
    missing_count: int
    missing_percentage: float
    severity: str


class WellCoveredSkill(BaseModel):
    """Skill present in >= 80% of candidate pool."""
    skill: str
    coverage_percentage: float


class SkillGapReport(BaseModel):
    """Aggregated skill gap analysis report across candidate pool for a specific job."""
    job_id: int
    job_title: str
    total_candidates_analyzed: int
    pool_readiness_score: float
    critical_gaps: List[SkillGapItem] = []
    moderate_gaps: List[SkillGapItem] = []
    minor_gaps: List[SkillGapItem] = []
    well_covered_skills: List[WellCoveredSkill] = []
    generated_at: str


class CandidateSkillGap(BaseModel):
    """Individual candidate's skill gaps against a specific job."""
    candidate_id: Optional[int] = None
    candidate_name: Optional[str] = None
    job_id: int
    job_title: str
    missing_required: List[str] = []
    missing_nice_to_have: List[str] = []


class CandidateGapDetail(BaseModel):
    """One missing skill for one candidate, contextualized against the pool."""
    skill: str
    category: str  # "required" | "nice_to_have"
    pool_coverage_percentage: float  # % of the candidate pool that already has this skill
    priority: str  # "high" | "medium" | "low"


class CandidateDevelopmentReport(BaseModel):
    """Full individual skill-gap development report — richer companion to
    CandidateSkillGap, adding fit score, readiness, matched skills, and
    pool-relative priority per gap. Does not replace CandidateSkillGap."""
    candidate_id: Optional[int] = None
    candidate_name: Optional[str] = None
    job_id: int
    job_title: str
    overall_fit_score: float
    readiness_level: str  # "ready" | "near_ready" | "developing" | "not_ready"
    matched_required: List[str] = []
    matched_nice_to_have: List[str] = []
    missing_required: List[CandidateGapDetail] = []
    missing_nice_to_have: List[CandidateGapDetail] = []
    development_recommendations: List[str] = []
    generated_at: str


# ---------------------------------------------------------------------------
# Interview Assistant schemas
# ---------------------------------------------------------------------------

class InterviewQuestion(BaseModel):
    question_number: int
    question_text: str
    question_type: str        # "Technical" | "Behavioral" | "Scenario-based"
    sub_type: str              # e.g. "Experience-based", "Communication", "Problem-solving"
    estimated_duration: str    # e.g. "3-5 min response"


class InterviewQuestionSet(BaseModel):
    job_id: int
    job_title: str
    question_type: str
    questions: List[InterviewQuestion]
    generated_at: str


class MCQOption(BaseModel):
    label: str   # "A" | "B" | "C" | "D"
    text: str


class PracticeQuestion(BaseModel):
    """Richer sibling of InterviewQuestion — adds difficulty and an
    optional multiple-choice format. Does not replace InterviewQuestion."""
    question_number: int
    question_text: str
    question_type: str
    sub_type: str
    estimated_duration: str
    difficulty: str                        # "Easy" | "Medium" | "Hard"
    question_format: str                   # "Open-ended" | "Multiple Choice"
    options: Optional[List[MCQOption]] = None      # populated only when question_format == "Multiple Choice"
    correct_option: Optional[str] = None            # e.g. "B" — MCQ only
    explanation: Optional[str] = None               # why the correct option is right — MCQ only


class PracticeQuestionSet(BaseModel):
    job_id: int
    job_title: str
    question_type: str
    difficulty: str
    question_format: str
    questions: List[PracticeQuestion]
    generated_at: str


class InterviewMessage(BaseModel):
    role: str
    content: str
    timestamp: str


class InterviewSessionResponse(BaseModel):
    session_id: int
    candidate_id: int
    candidate_name: Optional[str] = None
    job_id: int
    job_title: str
    status: str
    transcript: List[InterviewMessage] = []
    scheduled_at: Optional[str] = None
    created_at: str
    updated_at: str


class InterviewSessionCreate(BaseModel):
    candidate_id: int
    job_id: int
    scheduled_at: Optional[str] = None  # ISO datetime string; omit to mark in_progress immediately


class InterviewCandidateMessage(BaseModel):
    message: Optional[str] = None  # omit/None to generate the opening message





# ---------------------------------------------------------------------------
# Job schemas
# ---------------------------------------------------------------------------

class JobCreate(BaseModel):
    title: str
    description: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    seniority: Optional[str] = None
    min_experience_years: Optional[int] = None
    required_skills: Optional[List[str]] = None
    nice_to_have_skills: Optional[List[str]] = None
    status: Optional[str] = "open"


class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    seniority: Optional[str] = None
    min_experience_years: Optional[int] = None
    required_skills: Optional[List[str]] = None
    nice_to_have_skills: Optional[List[str]] = None
    status: Optional[str] = None


class JobResponse(BaseModel):
    job_id: int
    title: str
    description: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    seniority: Optional[str] = None
    min_experience_years: Optional[int] = None
    required_skills: List[str] = []
    nice_to_have_skills: List[str] = []
    status: str = "open"
    created_by: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_model(cls, db_obj):
        def parse_json_list(field):
            if not field:
                return []
            try:
                parsed = json.loads(field)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []

        return cls(
            job_id=db_obj.job_id,
            title=db_obj.title,
            description=db_obj.description,
            department=db_obj.department,
            location=db_obj.location,
            employment_type=db_obj.employment_type,
            seniority=db_obj.seniority,
            min_experience_years=db_obj.min_experience_years,
            required_skills=parse_json_list(db_obj.required_skills),
            nice_to_have_skills=parse_json_list(db_obj.nice_to_have_skills),
            status=db_obj.status,
            created_by=db_obj.created_by,
            created_at=db_obj.created_at,
        )


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
