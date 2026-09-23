from datetime import datetime
from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey
from database import Base


class Candidate(Base):
    __tablename__ = 'candidates'
    candidate_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    education = Column(Text, nullable=True)       # JSON string
    skills = Column(Text, nullable=True)           # JSON string
    experience = Column(Text, nullable=True)       # JSON string
    certifications = Column(Text, nullable=True)   # JSON string
    projects = Column(Text, nullable=True)         # JSON string
    resume_path = Column(String, nullable=True)    # original filename
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False)
    job_title = Column(String(100), nullable=False)   # "Recruiter" | "HR Manager" | "Admin"
    phone_number = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)


class InterviewSession(Base):
    __tablename__ = 'interview_sessions'
    session_id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey('candidates.candidate_id'), nullable=False)
    job_id = Column(Integer, ForeignKey('jobs.job_id'), nullable=False)
    status = Column(String(50), default="scheduled", nullable=False)  # scheduled | in_progress | completed
    transcript = Column(Text, nullable=True)   # JSON list of {"role": "...", "content": "...", "timestamp": "..."}
    scheduled_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey('users.user_id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

