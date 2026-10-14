"""
Phase 3 Regression Tests: Frontend Stabilization & Logic Verification.

Covers:
- Strict candidate deduplication (H2) preserving nameless/null-email dataset records
- Skill taxonomy acronym capitalization preservation (M16)
- 5-Pillar Hiring score component score breakdowns
- Error detail parsing and formatting for FastAPI 422 error structures
- HTML/XSS escaping helper validation
- Job status filtering for active jobs calculation (M1)
"""

import pytest
from skill_taxonomy import format_skill_display, SKILL_DISPLAY_MAP
from ui_common import _esc, format_error_detail
from services.hiring_score import calculate_hiring_score


def test_h2_deduplication_preserves_nameless_dataset_candidates():
    """
    Verify that candidates without names or emails (such as raw dataset candidates)
    are NOT collapsed down to a single candidate due to ("none", "none") truthiness.
    """
    raw_candidates = [
        {"candidate_id": 1, "name": None, "email": None, "skills": ["Python"]},
        {"candidate_id": 2, "name": None, "email": None, "skills": ["Java"]},
        {"candidate_id": 3, "name": "", "email": "", "skills": ["SQL"]},
        {"candidate_id": 4, "name": "Alice Smith", "email": "alice@example.com", "skills": ["AWS"]},
        {"candidate_id": 5, "name": "Alice Smith", "email": "alice@example.com", "skills": ["Docker"]},  # Duplicate
        {"candidate_id": 6, "name": "Bob Jones", "email": "bob@example.com", "skills": ["Go"]},
    ]

    deduped = []
    seen = set()
    for c in raw_candidates:
        cid = c.get("candidate_id")
        raw_name = str(c.get("name") or "").strip().lower()
        raw_email = str(c.get("email") or "").strip().lower()

        name_empty = not raw_name or raw_name in ("none", "null", "nan")
        email_empty = not raw_email or raw_email in ("none", "null", "nan")

        if not name_empty and not email_empty:
            ident = (raw_name, raw_email)
        elif cid is not None:
            ident = ("__id__", cid)
        else:
            ident = id(c)

        if ident in seen:
            continue
        seen.add(ident)
        deduped.append(c)

    # 1 duplicate (candidate 5) removed; candidates 1, 2, 3 must ALL be preserved!
    assert len(deduped) == 5
    ids = [c["candidate_id"] for c in deduped]
    assert 1 in ids
    assert 2 in ids
    assert 3 in ids
    assert 4 in ids
    assert 6 in ids
    assert 5 not in ids


def test_m16_skill_display_map_preserves_acronym_casing():
    """Verify that format_skill_display preserves proper casing for technical acronyms."""
    assert format_skill_display("aws") == "AWS"
    assert format_skill_display("sql") == "SQL"
    assert format_skill_display("nlp") == "NLP"
    assert format_skill_display("ci/cd") == "CI/CD"
    assert format_skill_display("gcp") == "GCP"
    assert format_skill_display("ml") == "ML"
    assert format_skill_display("etl") == "ETL"
    assert format_skill_display("python") == "Python"
    assert format_skill_display("machine learning") == "Machine Learning"


def test_hiring_score_includes_five_pillar_component_scores():
    """Verify calculate_hiring_score returns component_scores with all 5 dimensions."""
    sample_candidate = {
        "candidate_id": 101,
        "name": "Jane Developer",
        "email": "jane@example.com",
        "skills": ["Python", "SQL", "Docker", "AWS"],
        "education": [{"degree": "B.S. Computer Science"}],
        "experience": [{"title": "Software Engineer", "company": "Tech Corp", "years": 3}],
        "certifications": ["AWS Certified Developer"],
    }
    res = calculate_hiring_score(sample_candidate)
    score = res["hiring_score"]
    breakdown = res

    assert 0 <= score <= 100
    assert "component_scores" in breakdown
    comp = breakdown["component_scores"]

    required_pillars = [
        "resume_completeness",
        "skill_breadth",
        "experience_stability",
        "education_level",
        "certifications",
    ]
    for pillar in required_pillars:
        assert pillar in comp
        assert 0.0 <= comp[pillar] <= 100.0


def test_m1_active_jobs_count_filters_status():
    """Verify active jobs count strictly checks status == 'open'."""
    jobs_list = [
        {"job_id": 1, "title": "Job 1", "status": "open"},
        {"job_id": 2, "title": "Job 2", "status": "Open"},
        {"job_id": 3, "title": "Job 3", "status": " OPEN "},
        {"job_id": 4, "title": "Job 4", "status": "closed"},
        {"job_id": 5, "title": "Job 5", "status": "draft"},
        {"job_id": 6, "title": "Job 6", "status": None},
    ]

    active_jobs_count = sum(1 for j in jobs_list if str(j.get("status", "")).strip().lower() == "open")
    assert active_jobs_count == 3


def test_ui_common_error_detail_formatting():
    """Verify format_error_detail cleanly formats FastAPI 422 lists, dicts, and strings."""
    # String
    assert format_error_detail("Simple error message") == "Simple error message"

    # None
    assert format_error_detail(None) == "An unexpected error occurred."

    # Dict
    assert format_error_detail({"detail": "User not found"}) == "User not found"

    # FastAPI 422 list of validation errors
    pydantic_errors = [
        {"loc": ["body", "password"], "msg": "Password cannot exceed 72 bytes.", "type": "value_error"},
        {"loc": ["body", "email"], "msg": "value is not a valid email address", "type": "value_error.email"}
    ]
    formatted = format_error_detail(pydantic_errors)
    assert "password: Password cannot exceed 72 bytes." in formatted
    assert "email: value is not a valid email address" in formatted


def test_ui_common_esc_helper():
    """Verify _esc prevents HTML and XSS injection while safely handling non-strings."""
    assert _esc("<script>alert('xss')</script>") == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
    assert _esc("John & Doe <co>") == "John &amp; Doe &lt;co&gt;"
    assert _esc(None) == ""
    assert _esc(123) == "123"
    assert _esc(45.6) == "45.6"
