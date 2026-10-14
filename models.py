from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey
from database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Candidate(Base):
    __tablename__ = 'candidates'
    candidate_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=True)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    education = Column(Text, nullable=True)       # JSON string
    skills = Column(Text, nullable=True)           # JSON string
    experience = Column(Text, nullable=True)       # JSON string
    certifications = Column(Text, nullable=True)   # JSON string
    projects = Column(Text, nullable=True)         # JSON string
    resume_path = Column(String, nullable=True)    # original filename
    stage = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    deleted_at = Column(DateTime, nullable=True)


class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False)
    job_title = Column(String(100), nullable=False)   # "Candidate" | "Recruiter" | "Admin"
    phone_number = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    last_login_at = Column(DateTime, nullable=True)


class Job(Base):
    __tablename__ = 'jobs'
    job_id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    department = Column(String(100), nullable=True)
    location = Column(String(100), nullable=True)
    employment_type = Column(String(50), nullable=True)
    seniority = Column(String(50), nullable=True)
    min_experience_years = Column(Integer, nullable=True)
    required_skills = Column(Text, nullable=True)       # JSON string
    nice_to_have_skills = Column(Text, nullable=True)   # JSON string
    status = Column(String(50), default="open", nullable=False)
    created_by = Column(Integer, ForeignKey('users.user_id'), nullable=True)
    created_at = Column(DateTime, default=utc_now)


class InterviewSession(Base):
    __tablename__ = 'interview_sessions'
    session_id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey('candidates.candidate_id'), nullable=False)
    job_id = Column(Integer, ForeignKey('jobs.job_id'), nullable=False)
    status = Column(String(50), default="scheduled", nullable=False)  # scheduled | in_progress | completed
    transcript = Column(Text, nullable=True)   # JSON list of {"role": "...", "content": "...", "timestamp": "..."}
    feedback = Column(Text, nullable=True)     # JSON evaluation report
    interview_type = Column(String(50), default="mixed", nullable=True)
    difficulty = Column(String(50), default="Medium", nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey('users.user_id'), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class ResumeAnalysis(Base):
    __tablename__ = 'resume_analyses'
    analysis_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    candidate_id = Column(Integer, ForeignKey('candidates.candidate_id'), nullable=True)
    target_job_id = Column(Integer, ForeignKey('jobs.job_id'), nullable=True)
    analysis_data = Column(Text, nullable=False)  # JSON string
    created_at = Column(DateTime, default=utc_now)


class PracticeAnswer(Base):
    __tablename__ = 'practice_answers'
    answer_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    candidate_id = Column(Integer, ForeignKey('candidates.candidate_id'), nullable=True)
    job_id = Column(Integer, ForeignKey('jobs.job_id'), nullable=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(50), nullable=True)
    difficulty = Column(String(50), nullable=True)
    candidate_answer = Column(Text, nullable=False)
    feedback = Column(Text, nullable=False)  # JSON string
    created_at = Column(DateTime, default=utc_now)


class Application(Base):
    __tablename__ = 'applications'
    application_id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey('candidates.candidate_id'), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey('jobs.job_id'), nullable=True, index=True)
    recruiter_id = Column(Integer, ForeignKey('users.user_id'), nullable=True)
    stage = Column(String(50), default="new", nullable=False, index=True)  # new | shortlisted | interview | offered | hired | rejected
    notes = Column(Text, nullable=True)
    stage_history = Column(Text, nullable=True)  # JSON list of stage transitions
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    audit_id = Column(Integer, primary_key=True, autoincrement=True)
    actor_id = Column(Integer, ForeignKey('users.user_id'), nullable=True)
    actor_email = Column(String(255), nullable=True)
    action = Column(String(100), nullable=False)
    target_type = Column(String(100), nullable=True)
    target_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime, default=utc_now)


class LlmUsage(Base):
    __tablename__ = 'llm_usage'
    usage_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=True)
    feature = Column(String(100), nullable=False, default="unknown")
    provider = Column(String(50), nullable=True)
    model = Column(String(100), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True, nullable=False)
    error = Column(Text, nullable=True)
    input_chars = Column(Integer, nullable=True)
    output_chars = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class PlatformSetting(Base):
    __tablename__ = 'platform_settings'
    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    updated_by = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)



