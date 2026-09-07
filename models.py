from datetime import datetime
from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime
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
