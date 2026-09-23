"""
Unit tests for SmartHire AI Analytics Summary and Skill Stats.
"""

import pytest
from database import SessionLocal
from models import Candidate
from api import _compute_skill_stats
from schemas import AnalyticsSummary, SkillFrequency


def test_compute_skill_stats():
    """Verify that _compute_skill_stats returns valid counts matching the DB."""
    db = SessionLocal()
    try:
        candidates_total, resumes_parsed, all_skills, counts = _compute_skill_stats(db)
        actual_total = db.query(Candidate).count()
        assert candidates_total == actual_total
        assert resumes_parsed <= candidates_total
        assert len(counts) == len(set(all_skills))
        assert sum(counts.values()) == len(all_skills)
        if candidates_total > 0:
            assert resumes_parsed > 0
            assert len(all_skills) > 0
    finally:
        db.close()


def test_analytics_summary_schema():
    """Verify AnalyticsSummary schema serialization and validation."""
    summary = AnalyticsSummary(
        total_candidates=100,
        unique_skills=45,
        total_skill_occurrences=350,
        avg_skills_per_candidate=3.5,
        resumes_parsed=98,
    )
    assert summary.total_candidates == 100
    assert summary.unique_skills == 45
    assert summary.total_skill_occurrences == 350
    assert summary.avg_skills_per_candidate == 3.5
    assert summary.resumes_parsed == 98
